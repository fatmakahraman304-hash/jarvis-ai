"""Medya ve uygulamalar: YouTube'da çalma, Spotify, WhatsApp, Telegram, ses dosyasını yazıya çevirme, video özeti."""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser

from .. import llm
from ..config import env
from ..tools import S, _http_get, _path, _schema

IS_WIN = sys.platform.startswith("win")


def _open(uri):
    if IS_WIN:
        os.startfile(uri)  # type: ignore[attr-defined]
    else:
        webbrowser.open(uri)


def youtube_play(query):
    page = _http_get("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}))
    m = re.search(r'"videoId":"([\w-]{11})"', page)
    if not m:
        webbrowser.open("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}))
        return "Video bulunamadı, arama sonuçları açıldı."
    url = f"https://www.youtube.com/watch?v={m.group(1)}"
    webbrowser.open(url)
    t = re.search(r'"title":\{"runs":\[\{"text":"(.*?)"\}', page)
    return f"Oynatılıyor: {t.group(1) if t else url}"


def spotify_play(query):
    _open("spotify:search:" + urllib.parse.quote(query))
    if IS_WIN:
        try:
            from .computer import key_press
            time.sleep(4)
            key_press("tab")  # arama sonucuna odaklan
            time.sleep(0.3)
            key_press("enter")
        except Exception:
            pass
    return f"Spotify'da '{query}' açıldı."


def whatsapp_message(phone, text, send=True):
    phone = re.sub(r"\D", "", phone)
    if phone.startswith("0"):
        phone = "90" + phone[1:]
    _open(f"whatsapp://send?phone={phone}&text={urllib.parse.quote(text)}")
    if send and IS_WIN:
        try:
            from .computer import key_press
            time.sleep(6)
            key_press("enter")
            return f"WhatsApp mesajı gönderildi: +{phone}"
        except Exception as e:
            return f"Mesaj hazırlandı ama Enter'a basılamadı: {e}"
    return f"WhatsApp mesajı hazırlandı (+{phone}); göndermek için Enter'a bas."


def telegram_message(username, text):
    """Kendi botun üzerinden değil, Telegram masaüstünde sohbet açar."""
    _open(f"tg://resolve?domain={username.lstrip('@')}")
    try:
        from .computer import key_press, type_text
        time.sleep(4)
        type_text(text, press_enter=True)
        return f"Telegram mesajı gönderildi: @{username.lstrip('@')}"
    except Exception as e:
        return f"Sohbet açıldı, mesaj yazılamadı: {e}"


def open_file(path):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    _open(str(p))
    return f"Açıldı: {p.name}"


def _multipart(fields, file_field, filename, data, mime):
    b = uuid.uuid4().hex
    parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items()]
    parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
                 f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def transcribe_bytes(data, filename="ses.webm", mime="audio/webm", language="tr"):
    """Ses → yazı. Groq Whisper (ücretsiz) ya da OPENAI_API_KEY varsa OpenAI."""
    targets = []
    if env("GROQ_API_KEY"):
        targets.append(("https://api.groq.com/openai/v1/audio/transcriptions", env("GROQ_API_KEY"), "whisper-large-v3-turbo"))
    if env("OPENAI_API_KEY"):
        targets.append(("https://api.openai.com/v1/audio/transcriptions", env("OPENAI_API_KEY"), "whisper-1"))
    if not targets:
        raise RuntimeError("Ses yazıya çevirme için GROQ_API_KEY gerekli (ücretsiz).")
    err = ""
    for url, key, model in targets:
        fields = {"model": model, "response_format": "json"}
        if language:
            fields["language"] = language
        body, ctype = _multipart(fields, "file", filename, data, mime)
        req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read()).get("text", "").strip()
        except Exception as e:
            err = str(e)
    raise RuntimeError(f"Yazıya çevrilemedi: {err}")


def transcribe_verbose(data, filename="ses.webm", mime="audio/webm", language=""):
    """Ses → (metin, algılanan dil, zaman damgalı bölümler). Dil boşsa Whisper dili kendisi tanır."""
    targets = []
    if env("GROQ_API_KEY"):
        targets.append(("https://api.groq.com/openai/v1/audio/transcriptions", env("GROQ_API_KEY"), "whisper-large-v3-turbo"))
    if env("OPENAI_API_KEY"):
        targets.append(("https://api.openai.com/v1/audio/transcriptions", env("OPENAI_API_KEY"), "whisper-1"))
    if not targets:
        raise RuntimeError("Konuşma tanıma/çeviri için GROQ_API_KEY gerekli (ücretsiz).")
    err = ""
    for url, key, model in targets:
        fields = {"model": model, "response_format": "verbose_json"}
        if language:
            fields["language"] = language
        body, ctype = _multipart(fields, "file", filename, data, mime)
        req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read())
            segs = [{"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "")} for s in j.get("segments") or []]
            return j.get("text", "").strip(), j.get("language", language), segs
        except Exception as e:
            err = str(e)
    raise RuntimeError(f"Yazıya çevrilemedi: {err}")


def transcribe_audio(path, language="tr", summarize=False):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    if p.stat().st_size > 24_000_000:
        return "Dosya 25 MB'tan büyük; parçalara bölmen gerekiyor."
    mime = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
            ".webm": "audio/webm", ".mp4": "video/mp4", ".flac": "audio/flac"}.get(p.suffix.lower(), "application/octet-stream")
    text = transcribe_bytes(p.read_bytes(), p.name, mime, language)
    out = p.with_suffix(".txt")
    out.write_text(text, encoding="utf-8")
    res = {"metin_dosyası": str(out), "metin": text[:5000]}
    if str(summarize).lower() in ("true", "1"):
        res["not"] = "Özet için metni kullanarak kısa toplantı notu çıkar."
    return res


def youtube_transcript(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    if not m:
        return "Geçerli bir YouTube linki değil."
    vid = m.group(1)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        try:
            parts = YouTubeTranscriptApi().fetch(vid, languages=["tr", "en"])
            text = " ".join(p.text for p in parts)
        except AttributeError:
            parts = YouTubeTranscriptApi.get_transcript(vid, languages=["tr", "en"])
            text = " ".join(p["text"] for p in parts)
        return {"video": vid, "altyazı": text[:12000], "not": "Bunu kullanarak videoyu özetle."}
    except ImportError:
        pass
    except Exception as e:
        return f"Altyazı alınamadı: {e}"
    page = _http_get(f"https://www.youtube.com/watch?v={vid}")
    t = re.search(r'"title":"(.*?)"', page)
    d = re.search(r'"shortDescription":"(.*?)"', page)
    return {"video": vid, "başlık": t.group(1) if t else "", "açıklama": (d.group(1).encode().decode("unicode_escape", "ignore") if d else "")[:3000],
            "not": "Tam altyazı için 'pip install youtube-transcript-api' kur. Şimdilik başlık ve açıklamadan özetle."}


def ambient_listen(on=True):
    """Ortam sesi dinleme modunu açar/kapatır (arayüzde, tarayıcıda çalışır)."""
    on = str(on).lower() not in ("false", "0", "kapat", "off")
    return {"ui": "ambient", "on": on, "not": "Duman/yangın alarmı, cam kırılması, çığlık, bebek ağlaması, kapı zili, köpek havlaması gibi sesleri algılayınca uyarırım; "
                                               "önemli olanlar Telegram'a da gider. Ses bilgisayardan dışarı gönderilmez." if on else "Ortam dinleme kapatıldı."}


TOOLS = {
    "ambient_listen": (ambient_listen, _schema("Ortam sesi tanıma: mikrofonla sürekli dinleyip alarm, cam kırılması, bebek ağlaması, kapı zili, köpek gibi sesleri algılar ve uyarır.",
                                               {"on": {"type": "boolean"}}), False),
    "youtube_play": (youtube_play, _schema("YouTube'da arayıp ilk videoyu oynatır (şarkı, film fragmanı, video).", {"query": S("ne")}, ["query"]), False),
    "spotify_play": (spotify_play, _schema("Spotify'da şarkı/sanatçı/çalma listesi açar ve çalar.", {"query": S("ne")}, ["query"]), False),
    "whatsapp_message": (whatsapp_message, _schema("WhatsApp masaüstünden mesaj gönderir (onay gerekir).",
                                                   {"phone": S("telefon (05xx... veya 90...)"), "text": S("mesaj"), "send": {"type": "boolean"}},
                                                   ["phone", "text"]), True),
    "telegram_message": (telegram_message, _schema("Telegram masaüstünden bir kullanıcıya mesaj gönderir (onay gerekir).",
                                                   {"username": S("@kullanıcıadı"), "text": S("mesaj")}, ["username", "text"]), True),
    "open_file": (open_file, _schema("Dosyayı varsayılan programla açar (film, video, belge, resim).", {"path": S("dosya")}, ["path"]), False),
    "transcribe_audio": (transcribe_audio, _schema("Ses/video dosyasını yazıya çevirir (toplantı kaydı, sesli not).",
                                                   {"path": S("dosya"), "language": S("tr/en"), "summarize": {"type": "boolean"}}, ["path"]), False),
    "youtube_transcript": (youtube_transcript, _schema("YouTube videosunun altyazısını alır (özetlemek için).", {"url": S("link")}, ["url"]), False),
}
