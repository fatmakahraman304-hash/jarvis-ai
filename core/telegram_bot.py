"""Telegram köprüsü: telefondan, dünyanın her yerinden aynı beyne bağlan.

.env:
  TELEGRAM_BOT_TOKEN=...          (@BotFather'dan)
  TELEGRAM_ALLOWED_IDS=123456789  (sadece senin kullanıcı kimliğin; boşsa bot ilk yazana kimliğini söyler, cevap vermez)
"""
import asyncio
import json
import threading
import time
import urllib.parse
import urllib.request
import uuid

from . import brain, personas, voice
from .config import env, load_settings

API = "https://api.telegram.org/bot{token}/{method}"
_started = False
_voice_on = {}
_persona = {}


def _allowed():
    return {x.strip() for x in env("TELEGRAM_ALLOWED_IDS").split(",") if x.strip()}


def _call(method, params=None, timeout=40):
    url = API.format(token=env("TELEGRAM_BOT_TOKEN"), method=method)
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _send_file(method, field, chat_id, data, filename, mime, caption=""):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in (("chat_id", str(chat_id)), ("caption", caption)):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(API.format(token=env("TELEGRAM_BOT_TOKEN"), method=method), data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    urllib.request.urlopen(req, timeout=120).read()


def _download(file_id):
    info = _call("getFile", {"file_id": file_id})
    path = info["result"]["file_path"]
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{env('TELEGRAM_BOT_TOKEN')}/{path}", timeout=60) as r:
        return r.read(), path


def _send_audio(chat_id, audio_bytes, title):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in (("chat_id", str(chat_id)), ("title", title)):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"cevap.mp3\"\r\n"
                 f"Content-Type: audio/mpeg\r\n\r\n".encode() + audio_bytes + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(API.format(token=env("TELEGRAM_BOT_TOKEN"), method="sendAudio"),
                                 data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    urllib.request.urlopen(req, timeout=60).read()


def send(chat_id, text):
    for i in range(0, max(len(text), 1), 3900):
        _call("sendMessage", {"chat_id": chat_id, "text": text[i:i + 3900] or "…"})


def broadcast(text):
    if not env("TELEGRAM_BOT_TOKEN"):
        return
    for cid in _allowed():
        try:
            send(cid, text)
        except Exception as e:
            print("[telegram]", e)


HELP = ("Komutlar:\n/jarvis /friday /ultron — kişilik değiştir\n/ses — sesli cevabı aç/kapat\n"
        "/onay KOD — kritik işlemi onayla\n/iptal KOD — reddet\n/durum — bilgisayarın durumu\n/dosya YOL — bilgisayardan dosya gönder\n"
        "/kamera — bilgisayar kamerasından fotoğraf (izin açıksa)\n/dur — ACİL DURDURMA\n"
        "Sesli mesaj da gönderebilirsin. Fotoğraf/dosya gönderirsen İndirilenler'e kaydedilir.")


def _handle(chat_id, text):
    low = text.strip().lower()
    pid = _persona.get(chat_id) or load_settings().get("persona", "jarvis")
    if low in ("/start", "/help", "/yardim", "/yardım"):
        send(chat_id, personas.get(pid)["greeting"] + "\n\n" + HELP)
        return
    if low.lstrip("/") in personas.PERSONAS:
        _persona[chat_id] = low.lstrip("/")
        send(chat_id, personas.get(_persona[chat_id])["greeting"])
        return
    if low == "/ses":
        _voice_on[chat_id] = not _voice_on.get(chat_id, False)
        send(chat_id, "Sesli cevap " + ("açık" if _voice_on[chat_id] else "kapalı"))
        return
    if low in ("/dur", "/acil", "acil dur"):
        from .skills import control
        send(chat_id, "⛔ " + control.emergency_stop("Telegram"))
        return
    if low == "/durum":
        from . import tools
        st = tools.system_status()
        send(chat_id, "🖥 " + "\n".join(f"{k}: {v}" for k, v in st.items()) if isinstance(st, dict) else str(st))
        return
    if low.startswith("/dosya"):
        from .tools import _path
        p = _path(text.strip()[6:].strip())
        if not p.is_file():
            send(chat_id, f"Dosya bulunamadı: {p}")
            return
        if p.stat().st_size > 45_000_000:
            send(chat_id, "Dosya 45 MB'tan büyük, Telegram ile gönderilemez.")
            return
        _send_file("sendDocument", "document", chat_id, p.read_bytes(), p.name, "application/octet-stream", p.name)
        return
    if low == "/kamera":
        if not load_settings().get("allow_remote_camera"):
            send(chat_id, "Uzaktan kamera izni kapalı (bilgisayarda Ayarlar > Bağlantılar).")
            return
        from .server import _snap
        from . import memory
        _send_file("sendPhoto", "photo", chat_id, _snap(), "kamera.jpg", "image/jpeg", time.strftime("%d.%m %H:%M"))
        memory.log_action("camera_snapshot", {"from": "telegram"}, "ok", True)
        return
    if low.startswith(("/onay", "/iptal")):
        parts = low.split()
        if len(parts) < 2:
            send(chat_id, "Kod yaz: /onay abc123")
            return
        gen = brain.resolve(parts[1], approve=low.startswith("/onay"))
    else:
        gen = brain.chat(text, pid, session=f"tg_{chat_id}", source="telegram")
    _call("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    reply, confirms, meta = brain.collect(gen)
    for c in confirms:
        reply += f"\n\n⚠️ Onay gerekiyor: {c['text']}\nOnay: /onay {c['id']}   Reddet: /iptal {c['id']}"
    send(chat_id, reply or "…")
    if _voice_on.get(chat_id) and voice.available() and reply:
        try:
            audio = asyncio.run(voice.synthesize(reply[:1200], pid))
            _send_audio(chat_id, audio, personas.get(pid)["name"])
        except Exception as e:
            print("[telegram ses]", e)


def _loop():
    offset = 0
    print("[telegram] bot dinliyor")
    while True:
        try:
            res = _call("getUpdates", {"offset": offset, "timeout": 30}, timeout=40)
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                text = msg.get("text") or msg.get("caption")
                chat_id = msg.get("chat", {}).get("id")
                uid = str(msg.get("from", {}).get("id", ""))
                if not chat_id:
                    continue
                if uid in _allowed() and (msg.get("voice") or msg.get("audio") or msg.get("document") or msg.get("photo")):
                    threading.Thread(target=_safe_media, args=(chat_id, msg), daemon=True).start()
                    continue
                if not text:
                    continue
                if uid not in _allowed():
                    send(chat_id, f"Bu bot özeldir. Sahibiysen .env içine TELEGRAM_ALLOWED_IDS={uid} ekle ve JARVIS'i yeniden başlat.")
                    continue
                threading.Thread(target=_safe_handle, args=(chat_id, text), daemon=True).start()
        except Exception as e:
            print("[telegram]", e)
            time.sleep(5)


def _safe_media(chat_id, msg):
    try:
        if msg.get("voice") or msg.get("audio"):
            f = msg.get("voice") or msg.get("audio")
            data, path = _download(f["file_id"])
            from .skills.media import transcribe_bytes
            text = transcribe_bytes(data, "ses.ogg", "audio/ogg")
            send(chat_id, f"🎙 \"{text}\"")
            _voice_on.setdefault(chat_id, True)
            _handle(chat_id, text)
            return
        f = msg.get("document") or (msg.get("photo") or [None])[-1]
        data, path = _download(f["file_id"])
        from .tools import _path
        name = (msg.get("document") or {}).get("file_name") or f"telegram_{int(time.time())}.jpg"
        dst = _path("indirilenler") / name
        dst.write_bytes(data)
        send(chat_id, f"Kaydedildi: {dst}")
        if msg.get("caption"):
            _handle(chat_id, f"{msg['caption']} (dosya: {dst})")
    except Exception as e:
        send(chat_id, f"Hata: {e}")


def _safe_handle(chat_id, text):
    try:
        _handle(chat_id, text)
    except Exception as e:
        try:
            send(chat_id, f"Hata: {e}")
        except Exception:
            pass


def start():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="telegram").start()
