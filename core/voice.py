"""Ses üretimi: ücretsiz Microsoft Neural sesleri (edge-tts, API anahtarı gerekmez).

edge-tts kurulu değilse arayüz otomatik olarak tarayıcının kendi sesine düşer.
"""
import re

from . import personas
from .config import load_settings

try:
    import edge_tts  # type: ignore
except Exception:  # pragma: no cover
    edge_tts = None

_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_TR_WORDS = {"ve", "bir", "bu", "için", "ile", "efendim", "patron", "değil", "evet", "hayır", "ne", "nasıl", "şu", "çok"}


def detect_lang(text):
    if any(c in _TR_CHARS for c in text):
        return "tr"
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    return "tr" if len(words & _TR_WORDS) >= 1 else "en"


def available():
    return edge_tts is not None


def _adj(base, delta, unit):
    m = re.match(r"([+-]?\d+)", base)
    v = (int(m.group(1)) if m else 0) + int(delta or 0)
    return f"{'+' if v >= 0 else ''}{v}{unit}"


LANG_VOICES = {  # (erkek, kadın) Microsoft Neural sesleri
    "de": ("de-DE-ConradNeural", "de-DE-KatjaNeural"), "fr": ("fr-FR-HenriNeural", "fr-FR-DeniseNeural"), "es": ("es-ES-AlvaroNeural", "es-ES-ElviraNeural"),
    "it": ("it-IT-DiegoNeural", "it-IT-ElsaNeural"), "ru": ("ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"), "ar": ("ar-SA-HamedNeural", "ar-SA-ZariyahNeural"),
    "zh": ("zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural"), "ja": ("ja-JP-KeitaNeural", "ja-JP-NanamiNeural"), "ko": ("ko-KR-InJoonNeural", "ko-KR-SunHiNeural"),
    "pt": ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"), "nl": ("nl-NL-MaartenNeural", "nl-NL-ColetteNeural"), "el": ("el-GR-NestorasNeural", "el-GR-AthinaNeural"),
    "fa": ("fa-IR-FaridNeural", "fa-IR-DilaraNeural"), "hi": ("hi-IN-MadhurNeural", "hi-IN-SwaraNeural"), "uk": ("uk-UA-OstapNeural", "uk-UA-PolinaNeural"),
    "pl": ("pl-PL-MarekNeural", "pl-PL-ZofiaNeural"), "az": ("az-AZ-BabekNeural", "az-AZ-BanuNeural"), "sv": ("sv-SE-MattiasNeural", "sv-SE-SofieNeural"),
    "ro": ("ro-RO-EmilNeural", "ro-RO-AlinaNeural"), "bg": ("bg-BG-BorislavNeural", "bg-BG-KalinaNeural"),
}

MOODS = {  # (hız %, ton Hz) — duygusal tonlama
    "excited": (8, 6), "curious": (2, 4), "sad": (-8, -8), "serious": (-4, -5), "": (0, 0),
}


_voice_cache = {"t": 0, "v": []}


async def list_voices():
    """edge-tts ses listesi: Türkçe ve İngilizce (tüm aksanlar) + Türkçe de konuşabilen çok dilli sesler."""
    import time
    if not edge_tts:
        return []
    if _voice_cache["v"] and time.time() - _voice_cache["t"] < 86400:
        return _voice_cache["v"]
    raw = await edge_tts.list_voices()
    out = []
    for v in raw:
        name, loc = v.get("ShortName", ""), v.get("Locale", "")
        multi = "Multilingual" in name
        if not (loc.startswith(("tr-", "en-")) or multi):
            continue
        accent = {"en-GB": "İngiliz", "en-IE": "İrlandalı", "en-US": "Amerikan", "en-AU": "Avustralya", "en-CA": "Kanada", "en-IN": "Hint", "en-NZ": "Yeni Zelanda",
                  "en-ZA": "Güney Afrika", "en-SG": "Singapur", "en-HK": "Hong Kong", "en-KE": "Kenya", "en-NG": "Nijerya", "en-PH": "Filipin", "en-TZ": "Tanzanya",
                  "tr-TR": "Türkçe"}.get(loc, loc)
        gender = "erkek" if v.get("Gender") == "Male" else "kadın"
        short = name.split("-")[-1].replace("Neural", "").replace("Multilingual", "")
        out.append({"name": name, "locale": loc, "gender": gender, "multilingual": multi, "tr": loc.startswith("tr-") or multi,
                    "label": f"{short} · {accent} {gender}" + (" · çok dilli (Türkçe de konuşur)" if multi else "")})
    out.sort(key=lambda x: (not x["locale"].startswith("tr-"), not x["multilingual"], x["locale"], x["label"]))
    _voice_cache.update({"t": time.time(), "v": out})
    return out


async def synthesize(text, persona_id, lang="auto", mood="", voice=None, rate=None, pitch=None):
    """voice/rate/pitch verilirse (ses laboratuvarı önizlemesi) kaydedilmiş ayarların yerine onlar kullanılır."""
    if not edge_tts:
        raise RuntimeError("edge-tts kurulu değil")
    settings = load_settings()
    persona = personas.get(persona_id)
    if lang == "auto":
        lang = settings.get("voice_lang", "auto")
    if lang in LANG_VOICES:
        male, female = LANG_VOICES[lang]
        v = {"voice": female if persona["id"] == "friday" else male, "rate": "+0%", "pitch": "+0Hz"}
    else:
        if lang not in ("tr", "en"):
            lang = detect_lang(text)
        v = dict(persona["voice"][lang])
        pick = (settings.get("voice_pick", {}).get(persona["id"], {}) or {}).get(lang)
        if pick:
            v["voice"] = pick
    if voice:
        v = dict(v, voice=voice)
    user = dict(settings.get("voice", {}).get(persona["id"], {}))
    if rate is not None:
        user["rate"] = int(rate)
    if pitch is not None:
        user["pitch"] = int(pitch)
    mr, mp = MOODS.get(mood, (0, 0))
    if persona["id"] == "ultron":  # ULTRON duygusunu belli etmez, sadece hafifçe
        mr, mp = mr // 2, mp // 2
    rate = _adj(v["rate"], user.get("rate", 0) + mr, "%")
    pitch = _adj(v["pitch"], user.get("pitch", 0) + mp, "Hz")
    comm = edge_tts.Communicate(text, v["voice"], rate=rate, pitch=pitch)
    audio = bytearray()
    async for chunk in comm.stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)
