"""Optional Gemini Live speech output inspired by Mark LVI.

The normal JARVIS brain, tools, memory and confirmations still generate the
answer. This module only turns each completed answer sentence into PCM audio;
Edge TTS remains the automatic fallback.
"""
from __future__ import annotations

import base64
import secrets

from starlette.websockets import WebSocket, WebSocketDisconnect

from .config import env, load_settings

LIVE_MODEL = "gemini-3.1-flash-live-preview"
LIVE_VOICE = "Charon"
SAMPLE_RATE = 24000


async def live_voice_socket(websocket: WebSocket) -> None:
    """Persistent browser-to-Gemini Live TTS socket.

    Authentication is checked here because Starlette's HTTP middleware does not
    protect WebSocket handshakes. Remote clients must present the app token.
    """
    from .server import TOKEN

    peer = websocket.client.host if websocket.client else ""
    local = peer in ("127.0.0.1", "::1", "localhost", "testclient")
    supplied = websocket.query_params.get("token", "")
    if not local and (not TOKEN or not secrets.compare_digest(supplied, TOKEN)):
        await websocket.close(code=4401)
        return

    api_key = env("GEMINI_API_KEY")
    await websocket.accept()
    if not api_key:
        await websocket.send_json({"type": "error", "text": "Gemini API anahtarı bulunamadı."})
        await websocket.close(code=4403)
        return

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        await websocket.send_json({
            "type": "error",
            "text": "Gemini Live ses paketi kurulu değil. JARVIS güncellemesini tamamlayıp yeniden başlat.",
        })
        await websocket.close(code=1011)
        return

    voice_name = str(load_settings().get("live_voice_name") or LIVE_VOICE)
    if not voice_name or len(voice_name) > 40:
        voice_name = LIVE_VOICE

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription={},
        system_instruction=(
            "You are the speech output voice for JARVIS. The user message contains "
            "the exact text to speak. Read it verbatim in the same language, with "
            "natural pacing and clear pronunciation. Do not answer, summarize, "
            "translate, explain, add greetings, or omit anything. Speak only the "
            "provided text."
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        ),
    )

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            await websocket.send_json({
                "type": "ready", "model": LIVE_MODEL, "voice": voice_name, "sample_rate": SAMPLE_RATE
            })
            while True:
                msg = await websocket.receive_json()
                if not isinstance(msg, dict):
                    continue
                text = str(msg.get("text") or "").strip()
                request_id = str(msg.get("id") or "")[:64]
                if not text:
                    await websocket.send_json({"type": "done", "id": request_id, "empty": True})
                    continue
                if len(text) > 1800:
                    text = text[:1800]

                await session.send_client_content(
                    turns={"role": "user", "parts": [{"text": text}]},
                    turn_complete=True,
                )
                got_audio = False
                async for response in session.receive():
                    data = getattr(response, "data", None)
                    if data:
                        got_audio = True
                        await websocket.send_json({
                            "type": "audio",
                            "id": request_id,
                            "data": base64.b64encode(data).decode("ascii"),
                            "sample_rate": SAMPLE_RATE,
                        })
                    sc = getattr(response, "server_content", None)
                    if sc and getattr(sc, "turn_complete", False):
                        await websocket.send_json({
                            "type": "done", "id": request_id, "has_audio": got_audio
                        })
                        break
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "text": f"Gemini Live ses: {str(exc)[:240]}"})
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        try:
            await client.aio.aclose()
        except Exception:
            pass
