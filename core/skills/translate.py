"""Çeviri merkezi: metin çevirisi (birden çok dile aynı anda), konuşulan dili tanıma + çeviri (Whisper), SRT altyazı oluşturma,
iki yönlü canlı konuşma ve görüntülü görüşme çevirisi için sunucu tarafı."""
import json
import re

from ..tools import S, _path, _schema

LANGS = {"tr": "Türkçe", "en": "İngilizce", "de": "Almanca", "fr": "Fransızca", "es": "İspanyolca", "it": "İtalyanca", "ru": "Rusça",
         "ar": "Arapça", "zh": "Çince", "ja": "Japonca", "ko": "Korece", "pt": "Portekizce", "nl": "Felemenkçe", "el": "Yunanca",
         "fa": "Farsça", "hi": "Hintçe", "uk": "Ukraynaca", "pl": "Lehçe", "az": "Azerice", "sv": "İsveççe", "ro": "Romence", "bg": "Bulgarca"}
NAME2CODE = {v.lower(): k for k, v in LANGS.items()} | {"ingilizce": "en", "english": "en", "arabic": "ar", "turkish": "tr", "german": "de"}
WHISPER2CODE = {"turkish": "tr", "english": "en", "german": "de", "french": "fr", "spanish": "es", "italian": "it", "russian": "ru",
                "arabic": "ar", "chinese": "zh", "japanese": "ja", "korean": "ko", "portuguese": "pt", "dutch": "nl", "greek": "el",
                "persian": "fa", "hindi": "hi", "ukrainian": "uk", "polish": "pl", "azerbaijani": "az", "swedish": "sv", "romanian": "ro", "bulgarian": "bg"}


def code(lang):
    l = (lang or "").strip().lower()
    return l[:2] if l[:2] in LANGS and len(l) <= 5 else NAME2CODE.get(l, l[:2])


def translate_text(text, target="en", source="auto"):
    from .. import brain
    tc = code(target)
    tname = LANGS.get(tc, target)
    src = f"{LANGS.get(code(source), source)} dilindeki " if source and source != "auto" else ""
    out = brain.ask(f"Aşağıdaki {src}metni {tname} diline çevir. Anlamı, tonu ve biçimi koru. SADECE çeviriyi yaz, açıklama ekleme.\n\n<<<\n{text}\n>>>",
                    "Sen profesyonel, doğal ve akıcı çeviri yapan bir tercümansın.")
    return out.strip().strip("<>").strip()


def translate_multi(text, targets="en,de,ar"):
    return {LANGS.get(code(t), t): translate_text(text, t) for t in str(targets).split(",") if t.strip()}


def detect_and_translate_audio(data, filename, mime, target="tr", other="en"):
    """Ses → (otomatik dil tanıma) → yazı → hedef dile çeviri. Konuşulan dil hedef dilse 'other' diline çevirir (iki yönlü)."""
    from .media import transcribe_verbose
    text, lang, _ = transcribe_verbose(data, filename, mime, "")
    lc = WHISPER2CODE.get((lang or "").lower(), (lang or "")[:2])
    to = code(other) if lc == code(target) else code(target)
    tr = translate_text(text, to, lc) if text.strip() else ""
    return {"metin": text, "dil": lc, "dil_adı": LANGS.get(lc, lang), "çeviri": tr, "hedef": to, "hedef_adı": LANGS.get(to, to)}


def _srt_time(t):
    ms = int(round(float(t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_subtitles(path, translate_to="", language=""):
    from .media import transcribe_verbose
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    data = p.read_bytes()
    if len(data) > 24_000_000:
        return "Dosya 25 MB'tan büyük. Önce sesi ayır (ör. ffmpeg -i video.mp4 -vn -ac 1 -b:a 48k ses.mp3) ve onu ver."
    mime = {".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".webm": "audio/webm", ".ogg": "audio/ogg", ".mkv": "video/x-matroska"}.get(p.suffix.lower(), "application/octet-stream")
    text, lang, segs = transcribe_verbose(data, p.name, mime, language)
    if not segs:
        return "Konuşma bulunamadı."
    lines = [s["text"].strip() for s in segs]
    if translate_to:
        joined = "\n".join(f"{i + 1}|{t}" for i, t in enumerate(lines))
        tr = translate_text(f"Her satırı ayrı çevir, satır numaralarını ve '|' işaretini koru:\n{joined}", translate_to)
        mp = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^(\d+)\|(.*)$", tr, re.M)}
        lines = [mp.get(i + 1, l) for i, l in enumerate(lines)]
    srt = "\n".join(f"{i + 1}\n{_srt_time(s['start'])} --> {_srt_time(s['end'])}\n{lines[i]}\n" for i, s in enumerate(segs))
    out = p.with_suffix(f".{code(translate_to) or WHISPER2CODE.get((lang or '').lower(), 'xx')}.srt")
    out.write_text(srt, encoding="utf-8")
    return {"altyazı": str(out), "satır": len(segs), "konuşma_dili": lang, "çeviri": LANGS.get(code(translate_to), "") if translate_to else "yok",
            "ilk_satırlar": lines[:3]}


def translator_mode(lang_a="tr", lang_b="en"):
    return {"ui": "translator", "a": code(lang_a), "b": code(lang_b), "a_adı": LANGS.get(code(lang_a)), "b_adı": LANGS.get(code(lang_b))}


TOOLS = {
    "translate": (translate_multi, _schema("Metni bir veya birden çok dile aynı anda çevirir.", {"text": S("metin"), "targets": S("diller: en,de,ar veya İngilizce,Almanca")}, ["text"]), False),
    "make_subtitles": (make_subtitles, _schema("Video/ses dosyasına zaman damgalı SRT altyazı üretir; istenirse başka dile çevirir.",
                                               {"path": S("dosya"), "translate_to": S("çeviri dili (boş: aynı dil)"), "language": S("konuşma dili ipucu (boş: otomatik)")}, ["path"]), False),
    "translator_mode": (translator_mode, _schema("Canlı sesli tercüman modunu açar (iki kişi farklı dillerde konuşur, JARVIS anında çevirip seslendirir; görüntülü görüşme sesi de çevrilebilir).",
                                                 {"lang_a": S("1. dil (ör. tr)"), "lang_b": S("2. dil (ör. en, de, ar)")}), False),
}
