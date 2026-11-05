"""Web sunucusu: arayüz + API. Bilgisayardan, telefondan (aynı Wi-Fi) ve Telegram'dan aynı beyin."""
import contextlib
import json
import secrets
import threading
import time

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import brain, llm, memory, personas, tools, voice
from .config import VERSION, WEB, env, load_settings, save_settings

TOKEN = env("JARVIS_TOKEN")


class TokenAuth(BaseHTTPMiddleware):
    """127.0.0.1 dışından gelen her isteğe erişim anahtarı zorunlu."""

    async def dispatch(self, request, call_next):
        client = request.client.host if request.client else ""
        local = client in ("127.0.0.1", "::1", "localhost", "testclient")
        if request.url.path.startswith("/api") and not local and request.url.path != "/api/node/hello":
            given = request.headers.get("x-token") or request.query_params.get("token", "")
            if not TOKEN or not secrets.compare_digest(given, TOKEN):
                return JSONResponse({"error": "yetkisiz: JARVIS_TOKEN gerekli"}, status_code=401)
        return await call_next(request)


def _sse(gen):
    def run():
        try:
            for ev in gen:
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # beklenmeyen hata da arayüze ulaşsın
            yield f"data: {json.dumps({'type': 'error', 'text': f'{type(e).__name__}: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'text': ''})}\n\n"
    return StreamingResponse(run(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def index(request):
    # Google OAuth dönüşü (yönlendirme adresi kök dizin)
    code, st = request.query_params.get("code"), request.query_params.get("state")
    if code and st:
        from .skills import google
        try:
            email = google.finish_auth(st, code)
            memory.notify(f"Google hesabı bağlandı: {email}", "info")
        except Exception as e:
            memory.notify(f"Google bağlantısı başarısız: {e}", "error")
        return RedirectResponse("/")
    return FileResponse(WEB / "index.html")


def _is_local(request):
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost", "testclient")


async def google_connect(request):
    from .skills import google
    if not _is_local(request):
        return JSONResponse({"error": "Google bağlantısı bilgisayarın kendisinden yapılmalı."}, status_code=403)
    if not google.configured():
        return JSONResponse({"error": "Önce GOOGLE_CLIENT_ID ve GOOGLE_CLIENT_SECRET gir."}, status_code=400)
    port = request.url.port or 80
    return JSONResponse({"url": google.auth_url(f"http://127.0.0.1:{port}/")})


async def google_disconnect(request):
    from .skills import google
    if not _is_local(request):
        return JSONResponse({"error": "yasak"}, status_code=403)
    google.disconnect()
    return JSONResponse({"ok": True})


async def vision_api(request):
    """Tarayıcı kamerasından gelen kareyi analiz eder."""
    import base64
    body = await request.json()
    img = body.get("image", "")
    mime = "image/jpeg"
    if img.startswith("data:"):
        mime = img[5:img.index(";")]
        img = img.split(",", 1)[1]
    q = body.get("question") or "Ne görüyorsun? Kısa anlat; yazı veya QR kod varsa oku."
    try:
        from starlette.concurrency import run_in_threadpool
        ans = await run_in_threadpool(llm.vision, q + "\nKısa ve net Türkçe cevap ver.", base64.b64decode(img), mime)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    memory.add_message(body.get("session") or "main", "user", f"[kamera] {q}", body.get("persona", ""), "web")
    memory.add_message(body.get("session") or "main", "assistant", ans, body.get("persona", ""), "web")
    return JSONResponse({"text": ans})


async def transcribe_api(request):
    """Tarayıcıda kaydedilen sesi yazıya çevirir (Web Speech olmayan tarayıcılar için)."""
    from starlette.concurrency import run_in_threadpool
    from .skills.media import transcribe_bytes
    data = await request.body()
    mime = request.headers.get("content-type", "audio/webm").split(";")[0]
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav", "audio/mpeg": "mp3"}.get(mime, "webm")
    try:
        text = await run_in_threadpool(transcribe_bytes, data, f"ses.{ext}", mime, request.query_params.get("lang", "tr"))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return JSONResponse({"text": text})


async def voice_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import voiceid
    action = request.path_params.get("action", "profiles")
    try:
        if action == "profiles" and request.method == "GET":
            return JSONResponse(voiceid.profiles())
        if not _is_local(request) and action in ("enroll", "delete"):
            return JSONResponse({"error": "Ses tanıtma sadece bilgisayardan yapılabilir."}, status_code=403)
        if action == "delete":
            voiceid.delete(request.query_params.get("name", ""))
            return JSONResponse({"ok": True})
        data = await request.body()
        if action == "enroll":
            owner = request.query_params.get("owner")
            r = await run_in_threadpool(voiceid.enroll, request.query_params.get("name", "Sahip"), data,
                                        None if owner is None else owner == "1")
            return JSONResponse(r)
        if action == "identify":
            return JSONResponse(await run_in_threadpool(voiceid.identify, data))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"error": "bilinmeyen"}, status_code=404)


async def vault_api(request):
    from .skills import vault
    if not _is_local(request):
        return JSONResponse({"error": "Kasa sadece bilgisayardan yönetilebilir."}, status_code=403)
    action = request.path_params.get("action", "list")
    try:
        if action == "list":
            return JSONResponse(vault.entries())
        b = await request.json()
        if action == "save":
            if not b.get("name") or not b.get("secret"):
                return JSONResponse({"error": "ad ve şifre gerekli"}, status_code=400)
            vault.save_entry(b["name"].strip(), b.get("user", ""), b["secret"], b.get("url", ""), b.get("note", ""))
            return JSONResponse({"ok": True})
        if action == "delete":
            vault.delete_entry(b.get("name", ""))
            return JSONResponse({"ok": True})
        if action == "reveal":
            return JSONResponse({"secret": vault.reveal(b.get("name", ""))})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"error": "bilinmeyen"}, status_code=404)


async def geo_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import geo
    what = request.path_params["what"]
    q = request.query_params
    try:
        if what == "flights":
            box = [float(q.get(k)) for k in ("lamin", "lomin", "lamax", "lomax")] if q.get("lamin") else [-90, -180, 90, 180]
            return JSONResponse(await run_in_threadpool(geo.flights, *box, int(q.get("limit", 2500))))
        if what == "quakes":
            return JSONResponse(await run_in_threadpool(geo.earthquakes, q.get("period", "day"), float(q.get("min", 2.5))))
        if what == "ships":
            return JSONResponse(geo.ships())
        if what == "weather":
            return JSONResponse(await run_in_threadpool(tools.weather, f"{q.get('lat')},{q.get('lon')}"))
        if what == "geocode":
            return JSONResponse(await run_in_threadpool(geo.geocode, q.get("q", "")))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return JSONResponse({"error": "bilinmeyen"}, status_code=404)


async def sci_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import holo
    try:
        return JSONResponse(await run_in_threadpool(holo.molecule_data, request.query_params.get("name", "water")))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=404)


async def holo_file(request):
    from pathlib import Path
    p = Path(request.query_params.get("path", ""))
    if p.suffix.lower() not in (".stl", ".obj", ".glb", ".gltf") or not p.exists():
        return JSONResponse({"error": "dosya yok"}, status_code=404)
    return FileResponse(p)


async def holo_save(request):
    from .tools import _path
    import re as _re
    name = _re.sub(r"[^\w\-]+", "_", request.query_params.get("name", "model"))[:60] or "model"
    d = _path("belgeler") / "JARVIS_3D"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.stl"
    f.write_bytes(await request.body())
    memory.notify(f"3D model kaydedildi: {f}", "info")
    return JSONResponse({"path": str(f)})


async def gesture_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import computer, control
    if not _is_local(request):
        return JSONResponse({"error": "sadece bu bilgisayardan"}, status_code=403)
    a = request.path_params["action"]
    b = await request.json()
    try:
        if a == "mouse":
            r = await run_in_threadpool(control.gesture_mouse, b.get("action", "move"), b.get("x"), b.get("y"), b.get("amount", 0))
        elif a == "key":
            r = await run_in_threadpool(computer.key_press, b.get("keys", ""))
        elif a == "type":
            r = await run_in_threadpool(computer.type_text, b.get("text", ""))
        elif a == "media":
            r = await run_in_threadpool(tools.media_control, b.get("action", "play_pause"), b.get("steps", 1))
        elif a == "brightness":
            r = await run_in_threadpool(control.brightness_delta, b.get("delta", 0))
        elif a == "robot":
            r = await run_in_threadpool(control.robot_arm, b.get("base", 90), b.get("shoulder", 90), b.get("elbow", 90), b.get("gripper", 90), b.get("wrist", 90))
        else:
            return JSONResponse({"error": "bilinmeyen"}, status_code=404)
        return JSONResponse({"ok": True, "result": r})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def estop_api(request):
    from .skills import control
    if request.method == "POST":
        b = await request.json()
        return JSONResponse({"text": control.emergency_reset() if b.get("reset") else control.emergency_stop("arayüz düğmesi")})
    return JSONResponse({"active": control.ESTOP.is_set(), "safe_mode": control.STATE["safe_mode"], "online": control.STATE["online"]})


async def files_api(request):
    """Telefondan bilgisayardaki dosyalara erişim (erişim anahtarı gerekir)."""
    from pathlib import Path
    from .tools import _path
    q = request.query_params
    p = _path(q.get("path", ""))
    try:
        if request.path_params["action"] == "download":
            if not p.is_file():
                return JSONResponse({"error": "dosya yok"}, status_code=404)
            return FileResponse(p, filename=p.name)
        if not p.is_dir():
            return JSONResponse({"error": "klasör yok"}, status_code=404)
        items = []
        for c in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:500]:
            try:
                st = c.stat()
                items.append({"ad": c.name, "yol": str(c), "klasör": c.is_dir(), "kb": st.st_size // 1024 if c.is_file() else None,
                              "tarih": time.strftime("%d.%m.%Y %H:%M", time.localtime(st.st_mtime))})
            except Exception:
                pass
        return JSONResponse({"yol": str(p), "üst": str(p.parent) if p.parent != p else "", "öğeler": items,
                             "kısayollar": {k: str(_path(k)) for k in ("masaüstü", "belgeler", "indirilenler", "resimler", "ev")}})
    except PermissionError:
        return JSONResponse({"error": "erişim izni yok"}, status_code=403)


async def files_upload(request):
    from .tools import _path
    import re as _re
    name = _re.sub(r'[\\/:*?"<>|]', "_", request.query_params.get("name", "dosya"))
    d = _path(request.query_params.get("path", "indirilenler"))
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_bytes(await request.body())
    if request.query_params.get("quiet") != "1":
        memory.notify(f"Telefondan dosya geldi: {f}", "info")
    return JSONResponse({"path": str(f)})


async def camera_snapshot(request):
    """İzin verildiyse bilgisayar kamerasından anlık görüntü (telefon / Telegram için)."""
    s = load_settings()
    if not s.get("allow_remote_camera") and not _is_local(request):
        return JSONResponse({"error": "Uzaktan kamera izni kapalı (Ayarlar > Bağlantılar)."}, status_code=403)
    from starlette.concurrency import run_in_threadpool
    try:
        jpg = await run_in_threadpool(_snap)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    memory.log_action("camera_snapshot", {"from": request.client.host if request.client else ""}, "ok", True)
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def _snap():
    import cv2  # type: ignore
    cap = cv2.VideoCapture(0)
    ok, frame = False, None
    for _ in range(8):
        ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("kamera okunamadı")
    return cv2.imencode(".jpg", frame)[1].tobytes()


async def space_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import space
    try:
        if request.path_params["what"] == "sats":
            return JSONResponse(await run_in_threadpool(space.sat_elements, request.query_params.get("group", "stations")))
        if request.path_params["what"] == "craft":
            return JSONResponse(await run_in_threadpool(space.spacecraft_positions))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return JSONResponse({"error": "bilinmeyen"}, status_code=404)


async def watch_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import worldwatch as w
    what, q = request.path_params["what"], request.query_params
    try:
        if what == "events":
            return JSONResponse(await run_in_threadpool(w.eonet, int(q.get("days", 30)), q.get("category", "")))
        if what == "fires":
            return JSONResponse(await run_in_threadpool(w.firms, int(q.get("days", 1))))
        if what == "radar":
            return JSONResponse(await run_in_threadpool(w.radar_info))
        if what == "news":
            t = q.get("topic", "")
            return JSONResponse(await run_in_threadpool(w._cached, f"news{t}", 900, lambda: w.news_map(t)))
        if what == "ships":
            box = [float(q.get(k)) for k in ("lat1", "lon1", "lat2", "lon2")] if q.get("lat1") else [30, -6, 46, 37]
            return JSONResponse(await run_in_threadpool(w.ships_live, *box))
        if what == "gibs":
            data, d = await run_in_threadpool(w.gibs_image, q.get("date", ""))
            return Response(data, media_type="image/jpeg", headers={"X-Date": d, "Cache-Control": "max-age=3600"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return JSONResponse({"error": "bilinmeyen"}, status_code=404)


async def update_api(request):
    from starlette.concurrency import run_in_threadpool
    from . import updater
    if not _is_local(request):
        return JSONResponse({"error": "Güncelleme yalnızca bilgisayarın kendisinden yapılabilir."}, status_code=403)
    if request.method == "GET":
        if request.query_params.get("state"):
            return JSONResponse({**updater.STATE, "uzak": None, "sürüm": VERSION})
        r = await run_in_threadpool(updater.check, request.query_params.get("force") == "1")
        return JSONResponse({**r, "yedekler": updater.list_backups()})
    b = await request.json()
    if b.get("action") == "rollback":
        return JSONResponse(await run_in_threadpool(updater.rollback))
    return JSONResponse(await run_in_threadpool(updater.apply))


async def ambient_api(request):
    b = await request.json()
    label, level = str(b.get("label", ""))[:60], int(b.get("level", 1))
    _notify(f"Ortam sesi algılandı: {label} (%{round(float(b.get('score', 0)) * 100)})", "security" if level >= 2 else "info")
    memory.log_action("ambient_sound", {"ses": label, "skor": b.get("score")}, "algılandı", True)
    return JSONResponse({"ok": True})


async def music_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import music
    b = await request.json()
    try:
        r = await run_in_threadpool(music.music_compose, b.get("style", "lofi"), b.get("mood", ""), b.get("bpm", 0), b.get("bars", 16), b.get("key", ""), b.get("seed", 0), b.get("parts", "all"))
        return JSONResponse(r)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def finlab_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import financelab as fl
    what = request.path_params["what"]
    b = await request.json() if request.method == "POST" else {}
    fn = {"portfolio": lambda: fl.portfolio_show(), "add": lambda: fl.portfolio_add(b.get("symbol", ""), b.get("quantity", 0), b.get("buy_price", 0)),
          "remove": lambda: fl.portfolio_remove(b.get("symbol", "")),
          "backtest": lambda: fl.backtest(b.get("symbol", "XU100.IS"), b.get("strategy", "sma"), b.get("period", "5y"), b.get("short", 50), b.get("long", 200)),
          "montecarlo": lambda: fl.monte_carlo(b.get("initial", 100000), b.get("monthly", 5000), b.get("years", 20), b.get("annual_return", 10), b.get("volatility", 18),
                                               b.get("inflation", 0), b.get("goal", 0)),
          "loan": lambda: fl.loan_calc(b.get("principal", 1000000), b.get("annual_rate", 40), b.get("months", 36))}.get(what)
    if not fn:
        return JSONResponse({"error": "yok"}, status_code=404)
    try:
        r = await run_in_threadpool(fn)
        return JSONResponse(r if isinstance(r, dict) else {"mesaj": r})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


async def twin_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import twin
    what = request.path_params["what"]
    try:
        if what == "pc":
            return JSONResponse(await run_in_threadpool(twin.pc_twin_data), headers={"Cache-Control": "no-store"})
        if what == "home":
            return JSONResponse(await run_in_threadpool(twin.home_twin_data))
        if what == "toggle" and request.method == "POST":
            b = await request.json()
            r = await run_in_threadpool(twin.home_toggle, b.get("id", ""))
            memory.log_action("home_toggle", b, str(r), True)
            return JSONResponse({"sonuç": r})
        if what == "protein":
            return JSONResponse(await run_in_threadpool(twin.protein_data, request.query_params.get("q", "1CRN")))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return JSONResponse({"error": "yok"}, status_code=404)


async def node_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import nodes
    what = request.path_params["what"]
    if what == "hello":
        return JSONResponse(nodes.hello())
    if what == "info":
        return JSONResponse(await run_in_threadpool(nodes.self_info))
    if what == "run" and request.method == "POST":
        b = await request.json()
        r = await run_in_threadpool(nodes.handle_remote_run, b.get("text", ""), b.get("from", ""))
        if r is None:
            return JSONResponse({"error": "Bu bilgisayar uzaktan komut kabul etmiyor."}, status_code=403)
        return JSONResponse(r)
    if what == "list":
        r = await run_in_threadpool(nodes.node_list)
        return JSONResponse(r if isinstance(r, list) else [])
    if what == "add" and request.method == "POST":
        if not _is_local(request):
            return JSONResponse({"error": "Düğüm ekleme yalnızca bilgisayarın kendisinden."}, status_code=403)
        b = await request.json()
        return JSONResponse({"sonuç": await run_in_threadpool(nodes.node_add, b.get("url", ""), b.get("token", ""), b.get("name", ""))})
    if what == "discover":
        return JSONResponse({"sonuç": await run_in_threadpool(nodes.node_discover)})
    if what == "queue":
        r = nodes.node_queue_list()
        return JSONResponse(r if isinstance(r, list) else [])
    return JSONResponse({"error": "yok"}, status_code=404)


async def knowledge_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import knowledge as kn
    what = request.path_params["what"]
    try:
        if what == "list":
            r = kn.library_list()
            return JSONResponse(r if isinstance(r, list) else [])
        if what == "stats":
            r = kn.study_stats()
            return JSONResponse(r if isinstance(r, list) else [])
        b = await request.json() if request.method == "POST" else {}
        if what == "answer":
            return JSONResponse(kn.card_answer(b.get("card", 0), b.get("chosen", -1)))
        if what == "add":
            return JSONResponse({"sonuç": await run_in_threadpool(kn.library_add, b.get("path", ""), b.get("title", ""), b.get("tags", ""))})
        if what == "search":
            return JSONResponse({"sonuç": await run_in_threadpool(kn.library_search, b.get("query", ""), 8)})
        if what == "ask":
            return JSONResponse({"sonuç": await run_in_threadpool(kn.library_ask, b.get("question", ""), b.get("doc", ""))})
        if what == "remove":
            return JSONResponse({"sonuç": kn.library_remove(b.get("doc", ""))})
        if what == "graph":
            return JSONResponse(await run_in_threadpool(kn.knowledge_graph, b.get("topic", ""), b.get("doc", ""), b.get("ai", True)))
        if what == "review":
            r = kn.study_review(10)
            return JSONResponse(r if isinstance(r, dict) else {"note": r})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"error": "yok"}, status_code=404)


async def command_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import command as cmd
    if request.method == "GET":
        return JSONResponse(await run_in_threadpool(cmd.snapshot), headers={"Cache-Control": "no-store"})
    b = await request.json()
    a = b.get("action")
    try:
        if a == "mode":
            r = cmd.set_mode(b.get("mode", "normal"))
        elif a == "module":
            r = cmd.module_toggle(b.get("module", ""), b.get("on", True))
        elif a == "macro":
            r = await run_in_threadpool(cmd.macro_run, b.get("name", ""), b.get("persona", ""))
        elif a == "macro_save":
            r = cmd.macro_create(b.get("name", ""), b.get("steps", ""), b.get("trigger", ""))
        elif a == "macro_delete":
            r = cmd.macro_delete(b.get("name", ""))
        else:
            return JSONResponse({"error": "bilinmeyen işlem"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"sonuç": r})


async def translate_api(request):
    from starlette.concurrency import run_in_threadpool
    from .skills import translate as tr
    try:
        if request.path_params.get("kind") == "audio":
            q = request.query_params
            mime = request.headers.get("content-type", "audio/webm").split(";")[0]
            ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav", "video/webm": "webm"}.get(mime, "webm")
            data = await request.body()
            return JSONResponse(await run_in_threadpool(tr.detect_and_translate_audio, data, f"ses.{ext}", mime, q.get("target", "tr"), q.get("other", "en")))
        b = await request.json()
        return JSONResponse({"çeviri": await run_in_threadpool(tr.translate_text, b.get("text", ""), b.get("target", "en"), b.get("source", "auto"))})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


async def tasks_api(request):
    from .skills import automation
    return JSONResponse({"tasks": automation.list_tasks(), "todos": automation.todo_list(True)})


async def state(request):
    s = load_settings()
    return JSONResponse({
        "version": VERSION,
        "personas": personas.public(),
        "providers": llm.status(),
        "settings": s,
        "tts": voice.available(),
        "telegram": bool(env("TELEGRAM_BOT_TOKEN")),
        "pending": brain.pending_list(),
        "last_notification": memory.last_notification_id(),
        "google": _google_state(),
        "tool_count": len(tools.TOOLS),
        "home_assistant": bool(env("HA_URL") and env("HA_TOKEN")),
    })


def _google_state():
    try:
        from .skills import google
        return {"configured": google.configured(), "connected": google.connected(), "email": google.account()}
    except Exception:
        return {"configured": False, "connected": False, "email": ""}


async def chat(request):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "boş mesaj"}, status_code=400)
    source = body.get("source") or "web"
    spk = (body.get("speaker") or "").strip()[:40]
    if spk:
        text = f"[Konuşan: {spk}] {text}"
    guest = True if body.get("guest") else None
    if not _is_local(request) and source == "phone":
        pass
    return _sse(brain.chat(text, body.get("persona"), body.get("session") or "main", source, guest=guest))


async def confirm(request):
    body = await request.json()
    return _sse(brain.resolve(body.get("id", ""), bool(body.get("approve"))))


async def tts(request):
    text = (request.query_params.get("text") or "").strip()[:1500]
    if not text:
        return Response(status_code=400)
    if not voice.available():
        return JSONResponse({"error": "edge-tts yok"}, status_code=501)
    try:
        q = request.query_params
        audio = await voice.synthesize(text, q.get("persona", "jarvis"), q.get("lang", "auto"), q.get("mood", ""),
                                       q.get("voice") or None, q.get("rate") if q.get("rate") not in (None, "") else None,
                                       q.get("pitch") if q.get("pitch") not in (None, "") else None)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


async def voices_api(request):
    try:
        return JSONResponse(await voice.list_voices())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


async def system(request):
    return JSONResponse(tools.system_status(), )


async def processes(request):
    return JSONResponse(tools.top_processes(8, request.query_params.get("by", "ram")))


LOCAL_ONLY_SETTINGS = {"allow_remote_commands", "allow_remote_camera", "guest_mode", "voice_lock", "disabled_groups", "robot_port", "robot_url"}


async def settings(request):
    if request.method == "POST":
        patch = await request.json()
        if not _is_local(request):  # güvenlik ayarları yalnızca bilgisayarın kendisinden değiştirilebilir
            blocked = sorted(k for k in patch if k in LOCAL_ONLY_SETTINGS)
            patch = {k: v for k, v in patch.items() if k not in LOCAL_ONLY_SETTINGS}
            if blocked:
                memory.notify(f"Uzaktan güvenlik ayarı değiştirme denemesi engellendi: {', '.join(blocked)}", "security")
        return JSONResponse(save_settings(patch))
    return JSONResponse(load_settings())


async def memory_api(request):
    if request.method == "DELETE":
        memory.delete_fact(int(request.path_params["fid"]))
        return JSONResponse({"ok": True})
    if request.method == "POST":
        body = await request.json()
        fid = memory.add_fact(body.get("fact", ""), body.get("category", "genel"))
        return JSONResponse({"id": fid})
    return JSONResponse({"facts": memory.facts(), "reminders": memory.pending_reminders(),
                         "actions": memory.recent_actions(30)})


async def history(request):
    session = request.query_params.get("session", "main")
    if request.method == "DELETE":
        memory.clear_session(session)
        return JSONResponse({"ok": True})
    return JSONResponse(memory.history(session, int(request.query_params.get("limit", 50))))


async def notifications(request):
    return JSONResponse(memory.notifications_since(int(request.query_params.get("since", 0))))


async def models(request):
    pid = request.path_params["pid"]
    if pid not in llm.PROVIDERS:
        return JSONResponse({"error": "yok"}, status_code=404)
    refresh = request.query_params.get("refresh") == "1"
    return JSONResponse({"models": llm.list_models(pid, refresh) if llm.configured(pid) else [],
                         "selected": llm.pick_model(pid) if llm.configured(pid) else ""})


ALLOWED_KEYS = {p["key_env"] for p in llm.PROVIDERS.values() if p["key_env"]} | {
    "CUSTOM_BASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_IDS", "OLLAMA_BASE_URL",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "HA_URL", "HA_TOKEN", "OCTOPRINT_URL", "OCTOPRINT_KEY", "OPENAI_API_KEY"}


async def keys(request):
    """API anahtarlarını .env'ye yazar. Güvenlik: sadece bu bilgisayardan."""
    client = request.client.host if request.client else ""
    if client not in ("127.0.0.1", "::1", "localhost", "testclient"):
        return JSONResponse({"ok": False, "error": "Anahtarlar sadece bilgisayarın kendisinden değiştirilebilir."}, status_code=403)
    body = await request.json()
    from .config import ROOT
    import os
    env_file = ROOT / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    changed = 0
    for k, v in body.items():
        if k not in ALLOWED_KEYS or not isinstance(v, str) or "\n" in v:
            continue
        v = v.strip()
        lines = [ln for ln in lines if not ln.startswith(k + "=")]
        lines.append(f"{k}={v}")
        os.environ[k] = v
        changed += 1
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    llm._model_cache.clear()
    return JSONResponse({"ok": True, "changed": changed})


async def manifest(request):
    return FileResponse(WEB / "manifest.json", media_type="application/manifest+json")


# ---------------- arka plan: hatırlatıcılar ----------------
def _notify(text, kind="info"):
    from . import telegram_bot
    memory.notify(text, kind)
    try:
        telegram_bot.broadcast(("⏰ " if kind == "reminder" else "🔔 ") + text)
    except Exception:
        pass


def _scheduler():
    from .skills import automation, control, daily, finance, google, habits, semantic
    n = 0
    while True:
        try:
            for r in memory.due_reminders():
                _notify(f"Hatırlatma: {r['text']}", "reminder")
            automation.tick(_notify)
            habits.tick()
            semantic.index_tick()
            daily.alarm_tick(_notify)
            if n % 6 == 3:      # ~30 sn
                control.connectivity_tick(_notify)
            if n % 12 == 5:     # ~1 dk
                control.security_watch_tick(_notify)
            if n % 6 == 0:      # ~30 sn
                google.watch_tick(_notify)
            if n % 120 == 0:    # ~10 dk
                finance.check_alerts(_notify)
            if n % 720 == 30:   # ~saatte bir: yeni sürüm var mı (6 saatte bir gerçekten sorar)
                from . import updater
                updater.auto_check_tick(_notify)
            if n % 12 == 7:     # ~1 dk: uzak bilgisayar kuyruğu
                from .skills import nodes
                nodes.queue_tick()
        except Exception as e:
            print("[zamanlayıcı]", e)
        n += 1
        time.sleep(5)


def _startup():
    threading.Thread(target=_scheduler, daemon=True, name="scheduler").start()
    if env("TELEGRAM_BOT_TOKEN"):
        from . import telegram_bot
        telegram_bot.start()


routes = [
    Route("/", index),
    Route("/manifest.json", manifest),
    Route("/api/state", state),
    Route("/api/chat", chat, methods=["POST"]),
    Route("/api/confirm", confirm, methods=["POST"]),
    Route("/api/tts", tts),
    Route("/api/voices", voices_api),
    Route("/api/system", system),
    Route("/api/processes", processes),
    Route("/api/settings", settings, methods=["GET", "POST"]),
    Route("/api/memory", memory_api, methods=["GET", "POST"]),
    Route("/api/memory/{fid:int}", memory_api, methods=["DELETE"]),
    Route("/api/history", history, methods=["GET", "DELETE"]),
    Route("/api/notifications", notifications),
    Route("/api/models/{pid}", models),
    Route("/api/keys", keys, methods=["POST"]),
    Route("/api/google/connect", google_connect),
    Route("/api/google/disconnect", google_disconnect, methods=["POST"]),
    Route("/api/vision", vision_api, methods=["POST"]),
    Route("/api/transcribe", transcribe_api, methods=["POST"]),
    Route("/api/tasks", tasks_api),
    Route("/api/gesture/{action}", gesture_api, methods=["POST"]),
    Route("/api/estop", estop_api, methods=["GET", "POST"]),
    Route("/api/files/upload", files_upload, methods=["POST"]),
    Route("/api/files/{action}", files_api),
    Route("/api/camera/snapshot", camera_snapshot),
    Route("/api/geo/{what}", geo_api),
    Route("/api/space/{what}", space_api),
    Route("/api/watch/{what}", watch_api),
    Route("/api/translate", translate_api, methods=["POST"]),
    Route("/api/command", command_api, methods=["GET", "POST"]),
    Route("/api/knowledge/{what}", knowledge_api, methods=["GET", "POST"]),
    Route("/api/node/{what}", node_api, methods=["GET", "POST"]),
    Route("/api/twin/{what}", twin_api, methods=["GET", "POST"]),
    Route("/api/finlab/{what}", finlab_api, methods=["GET", "POST"]),
    Route("/api/music", music_api, methods=["POST"]),
    Route("/api/ambient", ambient_api, methods=["POST"]),
    Route("/api/update", update_api, methods=["GET", "POST"]),
    Route("/api/translate/{kind}", translate_api, methods=["POST"]),
    Route("/api/sci/molecule", sci_api),
    Route("/api/holo/file", holo_file),
    Route("/api/holo/save", holo_save, methods=["POST"]),
    Route("/api/voice/{action}", voice_api, methods=["GET", "POST"]),
    Route("/api/vault/{action}", vault_api, methods=["GET", "POST"]),
    Mount("/static", StaticFiles(directory=str(WEB)), name="static"),
]

@contextlib.asynccontextmanager
async def lifespan(app):
    _startup()
    yield


app = Starlette(routes=routes, middleware=[Middleware(TokenAuth)], lifespan=lifespan)
