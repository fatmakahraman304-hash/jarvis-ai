"""Medya ve uygulamalar: YouTube'da çalma, Spotify, WhatsApp, Telegram, ses dosyasını yazıya çevirme, video özeti."""
import json
import os
import re
import sys
import time
import urllib.error
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


def youtube_search(query, recent=False, n=5):
    params = {"search_query": query}
    if recent:
        params["sp"] = "CAI="  # yükleme tarihine göre (en yeni önce)
    page = _http_get("https://www.youtube.com/results?" + urllib.parse.urlencode(params))
    out = []
    for m in re.finditer(r'"videoRenderer":\{"videoId":"([\w-]{11})"(.*?)"title":\{"runs":\[\{"text":"(.*?)"\}', page):
        vid, title = m.group(1), m.group(3)
        tail = page[m.end():m.end() + 3000]
        ch = re.search(r'"ownerText":\{"runs":\[\{"text":"(.*?)"', tail)
        ago = re.search(r'"publishedTimeText":\{"simpleText":"(.*?)"', tail)
        if any(o["id"] == vid for o in out):
            continue
        out.append({"id": vid, "title": json.loads(f'"{title}"') if "\\" in title else title, "channel": ch.group(1) if ch else "", "when": ago.group(1) if ago else ""})
        if len(out) >= n:
            break
    if not out:  # sayfa biçimi değiştiyse kaba yedek
        out = [{"id": v, "title": "", "channel": "", "when": ""} for v in dict.fromkeys(re.findall(r'"videoId":"([\w-]{11})"', page))][:n]
    return out


def youtube_play(query, in_app=True):
    """YouTube'da arar; videoyu JARVIS'in içinde (panelde) açar. Maç özeti/haber gibi sorularda en yeni videoyu seçer."""
    recent = bool(re.search(r"özet|ozet|highlights|maç|mac |gol|son video|son bölüm|haber", query, re.I))
    try:
        res = youtube_search(query, recent=recent)
    except Exception as e:
        res = []
        err = str(e)
    if not res:
        webbrowser.open("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}))
        return "Video bulunamadı, arama sonuçları açıldı."
    v = res[0]
    url = f"https://www.youtube.com/watch?v={v['id']}"
    if not in_app:
        webbrowser.open(url)
        return f"Oynatılıyor: {v['title'] or url}"
    return {"ui": "video", "id": v["id"], "title": v["title"], "channel": v["channel"], "when": v["when"], "url": url,
            "diğerleri": [{"başlık": x["title"], "kanal": x["channel"], "ne zaman": x["when"]} for x in res[1:4]],
            "not": "Video JARVIS içinde açıldı. Kısaca hangi videoyu açtığını (başlık, kanal, ne zaman) söyle."}


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


def transcribe_gemini(data, mime="audio/wav", language="tr"):
    """Ses → yazı, Gemini ile (hafif model; ücretsiz kotası geniş). Sessizlikte uydurmasın diye 'BOŞ' döndürmesi istenir."""
    import base64
    from .. import gemini_native, llm
    if not llm.configured("gemini") or llm.key_bad("gemini"):
        raise RuntimeError("Gemini anahtarı yok/geçersiz")
    lang = {"tr": "Türkçe", "en": "İngilizce"}.get((language or "tr")[:2], "konuşulan dilde")
    prompt = (f"Bu ses kaydındaki konuşmayı {lang} olarak kelimesi kelimesine yazıya dök. Yalnızca söylenen metni yaz; "
              "açıklama, tırnak, zaman damgası ekleme. Anlaşılır konuşma yoksa sadece BOŞ yaz.")
    err = None
    for model in [m for m in (llm.light_model("gemini"), llm.pick_model("gemini")) if m]:
        body = {"contents": [{"role": "user", "parts": [{"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}, {"text": prompt}]}],
                "generationConfig": {"temperature": 0}}
        req = urllib.request.Request(f"{gemini_native.ROOT}/models/{model}:generateContent", data=json.dumps(body).encode(), method="POST",
                                     headers=gemini_native.headers(llm._key("gemini")))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.loads(r.read())
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "ignore")
            if e.code == 429:
                llm.mark_exhausted("gemini", model, b)
            llm.report_bad_key("gemini", e.code, b)
            err = RuntimeError(f"Gemini {e.code}")
            continue
        parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip().strip('"').strip()
        return "" if text.upper().rstrip(".") in ("BOŞ", "BOS", "EMPTY", "") else text
    raise err or RuntimeError("Gemini ile yazıya çevrilemedi")


def transcribe_bytes(data, filename="ses.webm", mime="audio/webm", language="tr", info=None):
    """Ses → yazı. 'Sadece Gemini' açıksa önce Gemini; sonra Groq Whisper (ücretsiz) ya da OpenAI."""
    from .. import llm
    gem_err = None
    if llm.configured("gemini") and (llm.only_gemini() or not (env("GROQ_API_KEY") or env("OPENAI_API_KEY"))) and mime in ("audio/wav", "audio/ogg", "audio/mpeg", "audio/mp3", "audio/flac", "audio/aac"):
        try:
            t = transcribe_gemini(data, mime, language)
            if info is not None:
                info["engine"] = "Gemini"
            return t
        except Exception as e:
            gem_err = e
    targets = []
    if env("GROQ_API_KEY"):
        targets.append(("https://api.groq.com/openai/v1/audio/transcriptions", env("GROQ_API_KEY"), "whisper-large-v3-turbo"))
    if env("OPENAI_API_KEY"):
        targets.append(("https://api.openai.com/v1/audio/transcriptions", env("OPENAI_API_KEY"), "whisper-1"))
    if not targets:
        raise RuntimeError(f"Ses yazıya çevrilemedi ({gem_err})." if gem_err else "Ses yazıya çevirme için Gemini ya da Groq anahtarı gerekli (ücretsiz).")
    err = ""
    for url, key, model in targets:
        if info is not None:
            info["engine"] = "Whisper"
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
    "youtube_play": (youtube_play, _schema("YouTube'da arayıp videoyu JARVIS içinde oynatır (şarkı, fragman, MAÇ ÖZETİ, haber videosu; özet/maç aramalarında en yenisi seçilir).", {"query": S("ne")}, ["query"]), False),
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
