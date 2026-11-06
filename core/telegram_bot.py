"""Telegram köprüsü: telefondan, dünyanın her yerinden aynı beyne bağlan.

.env:
  TELEGRAM_BOT_TOKEN=...          (@BotFather'dan)
  TELEGRAM_ALLOWED_IDS=123456789  (sadece senin kullanıcı kimliğin; boşsa bot ilk yazana kimliğini söyler, cevap vermez)
"""
import asyncio
import json
import re
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


def _cert_diagnosis():
    """api.telegram.org'a giderken araya giren sertifikayı tanımlar (hiçbir veri göndermeden, yalnızca sertifikayı okur)."""
    import socket
    import ssl
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("api.telegram.org", 443), timeout=10) as raw, ctx.wrap_socket(raw, server_hostname="api.telegram.org") as tls:
            der = tls.getpeercert(binary_form=True)
        issuer = ""
        try:
            from cryptography import x509
            c = x509.load_der_x509_certificate(der)
            issuer = c.issuer.rfc4514_string()
        except Exception:
            m = re.findall(rb"[\x20-\x7e]{6,}", der)
            issuer = ", ".join(x.decode() for x in m[:6])
    except Exception as e:
        return f"sertifika okunamadı ({e}). İnternet bağlantısını kontrol et."
    hint = ("Bir antivirüs/güvenlik programı (" + issuer + ") şifreli bağlantıları denetliyor. JARVIS artık Windows'un güvendiği sertifikaları kullanıyor; "
            "yine olmuyorsa o programın 'HTTPS/SSL tarama' ayarında python.exe'yi istisnaya ekle.") if any(k in issuer.lower() for k in ("kaspersky", "avast", "avg", "eset", "bitdefender", "norton", "mcafee", "fortinet", "sophos", "zscaler", "trend")) else (
            f"Bağlantıya araya giren bir sertifika var ({issuer}). Bu ağ (modem, iş/okul ağı ya da internet sağlayıcısı) Telegram'ı engelliyor ya da yönlendiriyor olabilir. "
            "Edge'de https://api.telegram.org adresini aç: sertifika uyarısı çıkıyorsa engel ağda; farklı ağ/VPN dene ya da .env'e TELEGRAM_PROXY=http://adres:port ekle.")
    return hint


def _allowed():
    return {x.strip() for x in env("TELEGRAM_ALLOWED_IDS").split(",") if x.strip()}


def _urlopen(req, timeout=40):
    """Telegram'a özel açıcı. Sertifikalar Windows'un kendi güven deposuyla doğrulanır (truststore; antivirüsün HTTPS taraması
    gibi Windows'a tanıtılmış sertifikalar da kabul edilir). .env TELEGRAM_PROXY varsa yalnızca Telegram trafiği o vekilden geçer."""
    handlers = []
    try:
        import ssl
        import truststore  # type: ignore
        handlers.append(urllib.request.HTTPSHandler(context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
    except Exception:
        pass
    px = env("TELEGRAM_PROXY")
    if px:
        handlers.append(urllib.request.ProxyHandler({"https": px, "http": px}))
    if handlers:
        return urllib.request.build_opener(*handlers).open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _token():
    """Kopyalarken bulaşan tırnak, boşluk, < > ve 'bot' önekini temizler."""
    t = env("TELEGRAM_BOT_TOKEN").strip().strip('"\'<>').replace(" ", "")
    if t.lower().startswith("bot") and ":" in t:
        t = t[3:]
    return t


def _token_diagnosis():
    from .config import ROOT
    t = _token()
    lines = []
    try:
        lines = [ln for ln in (ROOT / ".env").read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip().startswith("TELEGRAM_BOT_TOKEN")]
    except Exception:
        pass
    probs = []
    if len(lines) > 1:
        probs.append(f".env içinde {len(lines)} tane TELEGRAM_BOT_TOKEN satırı var; sadece BİR tane bırak")
    if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{30,50}", t):
        if ":" not in t:
            probs.append("token'da ':' yok (bot kullanıcı adını ya da t.me linkini kopyalamış olabilirsin)")
        else:
            a, b = t.split(":", 1)
            probs.append(f"biçim hatalı: ':' öncesi {len(a)} karakter (rakam olmalı, 8-10), sonrası {len(b)} karakter (yaklaşık 35 olmalı)")
    shown = (t[:4] + "…" + t[-3:]) if len(t) > 10 else "(boş/çok kısa)"
    return (f"Telegram token'ı reddedildi (401). Okunan token: {shown}, uzunluk {len(t)}. "
            + ("Sorun: " + "; ".join(probs) + ". " if probs else "Biçim doğru görünüyor; bu token iptal edilmiş/yenilenmiş olabilir. ")
            + "@BotFather > /mybots > botun > API Token'dan güncel token'ı kopyalayıp .env'e yaz ve JARVIS'i yeniden başlat.")


def _call(method, params=None, timeout=40):
    url = API.format(token=_token(), method=method)
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with _urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _send_file(method, field, chat_id, data, filename, mime, caption=""):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in (("chat_id", str(chat_id)), ("caption", caption)):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(API.format(token=_token(), method=method), data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    _urlopen(req, timeout=120).read()


def _download(file_id):
    info = _call("getFile", {"file_id": file_id})
    path = info["result"]["file_path"]
    with _urlopen(f"https://api.telegram.org/file/bot{_token()}/{path}", timeout=60) as r:
        return r.read(), path


def _send_audio(chat_id, audio_bytes, title):
    """Sesli cevap: önce Telegram 'sesli mesaj' (oynatma balonu), olmazsa mp3 dosyası olarak."""
    try:
        _send_file("sendVoice", "voice", chat_id, audio_bytes, "cevap.mp3", "audio/mpeg", "")
    except Exception:
        _send_file("sendAudio", "audio", chat_id, audio_bytes, "cevap.mp3", "audio/mpeg", title)


def voice_enabled(chat_id):
    if chat_id in _voice_on:
        return _voice_on[chat_id]
    return bool((load_settings().get("telegram_voice") or {}).get(str(chat_id), False))


def set_voice(chat_id, on):
    _voice_on[chat_id] = bool(on)
    from .config import save_settings
    tv = dict(load_settings().get("telegram_voice") or {})
    tv[str(chat_id)] = bool(on)
    save_settings({"telegram_voice": tv})


def speak_to(chat_id, text, pid):
    if not (text and voice.available()):
        return False
    try:
        clean = re.sub(r"[*_`#>\[\]]", "", text)
        audio = asyncio.run(voice.synthesize(clean[:1500], pid))
        _call("sendChatAction", {"chat_id": chat_id, "action": "record_voice"})
        _send_audio(chat_id, audio, personas.get(pid)["name"])
        return True
    except Exception as e:
        print("[telegram ses]", e)
        return False


# ---------------- ekran görüntüsü ----------------
def screenshot_jpeg(max_w=2560):
    try:
        from PIL import ImageGrab
    except ImportError:
        raise RuntimeError("Ekran görüntüsü için 'pillow' gerekli.")
    import io
    img = ImageGrab.grab(all_screens=True)
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=82)
    return buf.getvalue()


def send_screenshot(chat_id):
    if not load_settings().get("allow_remote_screen", True):
        send(chat_id, "Uzaktan ekran görüntüsü izni kapalı (bilgisayarda Ayarlar > Bağlantılar).")
        return False
    from . import memory
    _call("sendChatAction", {"chat_id": chat_id, "action": "upload_photo"})
    _send_file("sendPhoto", "photo", chat_id, screenshot_jpeg(), "ekran.jpg", "image/jpeg", "🖥 Ekran · " + time.strftime("%d.%m %H:%M:%S"))
    memory.log_action("screenshot_to_phone", {"from": "telegram"}, "ok", True)
    return True


def screenshot_to_phone():
    """Araç: ekran görüntüsünü izinli Telegram hesap(lar)ına gönderir."""
    if not env("TELEGRAM_BOT_TOKEN") or not _allowed():
        return "Telegram bağlı değil (TELEGRAM_BOT_TOKEN ve TELEGRAM_ALLOWED_IDS gerekli)."
    n = 0
    for cid in _allowed():
        try:
            n += bool(send_screenshot(cid))
        except Exception as e:
            return f"Gönderilemedi: {e}"
    return "Ekran görüntüsü telefonuna gönderildi." if n else "Gönderilmedi (uzaktan ekran izni kapalı olabilir)."


# ---------------- uzaktan kumanda paneli ----------------
def _kb(rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


PANEL = [[("🔒 Kilitle", "lock"), ("😴 Uyut", "sleep")],
         [("📸 Ekran", "screen"), ("🖥 Durum", "status")],
         [("🔇 Sesi kapat/aç", "mute"), ("☀️ Brifing", "brief")],
         [("🔊 Sesli cevap", "voice"), ("⛔ ACİL DUR", "stop")]]


def send_panel(chat_id):
    _call("sendMessage", {"chat_id": chat_id, "text": "🎛 Uzaktan kumanda — bir düğmeye bas:", "reply_markup": _kb(PANEL)})


def _on_button(chat_id, msg_id, data):
    """Panel düğmeleri. Uyutma iki adımlıdır (önce 'emin misin?')."""
    from . import memory, tools
    pid = _persona.get(chat_id) or load_settings().get("persona", "jarvis")
    if data == "lock":
        r = tools.lock_pc()
        memory.log_action("lock_pc", {"from": "telegram"}, r, True)
        send(chat_id, "🔒 " + r)
    elif data == "sleep":
        _call("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "😴 Bilgisayar uyutulsun mu? (açık işlerin kaydedildiğinden emin ol)",
                                  "reply_markup": _kb([[("✅ Evet, uyut", "sleep_yes"), ("✖ Vazgeç", "sleep_no")]])})
        return
    elif data == "sleep_yes":
        _call("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "😴 Uyutuluyor… iyi geceler."})
        memory.log_action("power", {"action": "sleep", "from": "telegram"}, "onaylandı", True)
        threading.Timer(2.0, lambda: tools.power("sleep")).start()  # önce mesaj gitsin
        return
    elif data == "sleep_no":
        _call("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": "Uyutma iptal edildi.", "reply_markup": _kb(PANEL)})
        return
    elif data == "screen":
        send_screenshot(chat_id)
    elif data == "status":
        st = tools.system_status()
        send(chat_id, "🖥 " + ("\n".join(f"{k}: {v}" for k, v in st.items()) if isinstance(st, dict) else str(st)))
    elif data == "mute":
        send(chat_id, "🔇 " + tools.media_control("mute"))
    elif data == "brief":
        from .skills import automation
        txt = automation.morning_briefing(_persona.get(chat_id, ""))
        send(chat_id, "☀️ " + txt)
        if voice_enabled(chat_id):
            speak_to(chat_id, txt, pid)
    elif data == "voice":
        set_voice(chat_id, not voice_enabled(chat_id))
        send(chat_id, "🔊 Sesli cevap " + ("AÇIK — artık sesli mesajla da cevap vereceğim." if voice_enabled(chat_id) else "kapalı."))
    elif data == "stop":
        from .skills import control
        send(chat_id, "⛔ " + control.emergency_stop("Telegram"))
    else:
        return
    if data != "stop":
        send_panel(chat_id)  # panel hep en altta dursun


def _safe_button(chat_id, msg_id, data):
    try:
        _on_button(chat_id, msg_id, data)
    except Exception as e:
        try:
            send(chat_id, f"Hata: {e}")
        except Exception:
            pass


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


HELP = ("Komutlar:\n/jarvis /friday — kişilik değiştir\n/ses — sesli cevabı aç/kapat\n"
        "/onay KOD — kritik işlemi onayla\n/iptal KOD — reddet\n/durum — bilgisayarın durumu\n/dosya YOL — bilgisayardan dosya gönder\n"
        "/kamera — bilgisayar kamerasından fotoğraf (izin açıksa)\n/ekran — ekran görüntüsü\n/panel — düğmeli uzaktan kumanda (kilitle, uyut, ekran…)\n"
        "/kilitle — bilgisayarı kilitle\n/brifing — sabah brifingi\n/dur — ACİL DURDURMA\n"
        "Sesli mesaj da gönderebilirsin. Fotoğraf/dosya gönderirsen İndirilenler'e kaydedilir.")


COMMANDS = [("panel", "Düğmeli uzaktan kumanda"), ("ekran", "Ekran görüntüsü"), ("kilitle", "Bilgisayarı kilitle"),
            ("durum", "Bilgisayarın durumu"), ("brifing", "Sabah brifingi"), ("ses", "Sesli cevap aç/kapat"),
            ("kamera", "Kamera fotoğrafı"), ("jarvis", "JARVIS'e geç"), ("friday", "FRIDAY'e geç"),
            ("dur", "ACİL DURDURMA"), ("yardim", "Komutlar")]


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
        set_voice(chat_id, not voice_enabled(chat_id))
        send(chat_id, "🔊 Sesli cevap " + ("açık" if voice_enabled(chat_id) else "kapalı"))
        return
    if low in ("/panel", "/kumanda", "/menu", "/menü"):
        send_panel(chat_id)
        return
    if low in ("/ekran", "/screenshot", "/ss"):
        send_screenshot(chat_id)
        return
    if low in ("/kilitle", "/kilit", "/lock"):
        _on_button(chat_id, 0, "lock")
        return
    if low in ("/dur", "/acil", "acil dur"):
        from .skills import control
        send(chat_id, "⛔ " + control.emergency_stop("Telegram"))
        return
    if low in ("/brifing", "/sabah", "/briefing"):
        from .skills import automation
        send(chat_id, "☀️ " + automation.morning_briefing(_persona.get(chat_id, "")))
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
    if voice_enabled(chat_id) and reply:
        speak_to(chat_id, reply, pid)


def _loop():
    offset = 0
    print("[telegram] bot dinliyor")
    try:  # telefondaki "/" menüsü
        _call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]})
    except Exception:
        pass
    while True:
        try:
            res = _call("getUpdates", {"offset": offset, "timeout": 30}, timeout=40)
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                cq = upd.get("callback_query")
                if cq:
                    cuid = str(cq.get("from", {}).get("id", ""))
                    m = cq.get("message") or {}
                    ok = cuid in _allowed()
                    try:
                        _call("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "" if ok else "Yetkin yok."})
                    except Exception:
                        pass
                    if ok and m.get("chat", {}).get("id"):
                        threading.Thread(target=_safe_button, args=(m["chat"]["id"], m.get("message_id"), cq.get("data", "")), daemon=True).start()
                    continue
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
            fails = getattr(_loop, "fails", 0) + 1
            _loop.fails = fails
            if "401" in str(e) and "Unauthorized" in str(e):
                if fails == 1:
                    msg = _token_diagnosis()
                    print("[telegram]", msg)
                    try:
                        from . import memory
                        memory.notify(msg, "error")
                    except Exception:
                        pass
                time.sleep(600)  # geçersiz token: tekrar tekrar deneme
                continue
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                if fails == 1:
                    print("[telegram]", _cert_diagnosis())
                    try:
                        from . import memory
                        memory.notify("Telegram bağlanamıyor: " + _cert_diagnosis(), "error")
                    except Exception:
                        pass
            elif fails <= 3 or fails % 20 == 0:
                print("[telegram]", e)
            time.sleep(min(300, 5 * fails))  # sürekli hata basmasın: giderek seyrek dene
            continue
        _loop.fails = 0


def _safe_media(chat_id, msg):
    try:
        if msg.get("voice") or msg.get("audio"):
            f = msg.get("voice") or msg.get("audio")
            data, path = _download(f["file_id"])
            from .skills.media import transcribe_bytes
            text = transcribe_bytes(data, "ses.ogg", "audio/ogg")
            send(chat_id, f"🎙 \"{text}\"")
            if chat_id not in _voice_on and str(chat_id) not in (load_settings().get("telegram_voice") or {}):
                _voice_on[chat_id] = True  # sesle yazana sesle cevap (kalıcı ayar /ses ile)
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
