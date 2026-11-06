"""Optional, user-supplied licensed film voice clips.

Files live only in data/voice_assets (never in the repository). A manifest maps
an exact spoken phrase to a relative audio filename. Missing clips fall back to
the existing Neural TTS engine.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "data" / "voice_assets"
MANIFEST = ASSET_DIR / "manifest.json"
PERSONAS = {"jarvis", "friday", "ultron"}
LANGUAGES = {"tr", "en"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm"}


def _key(text):
    return re.sub(r"\\s+", " ", (text or "").strip()).casefold()


def find_clip(persona, lang, text):
    """Return a validated local clip path for an exact phrase, or None."""
    persona = (persona or "").lower()
    lang = (lang or "").lower().split("-")[0]
    if persona not in PERSONAS or lang not in LANGUAGES or not text:
        return None
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        relative = manifest.get(persona, {}).get(lang, {}).get(_key(text))
        if not isinstance(relative, str):
            return None
        candidate = (ASSET_DIR / relative).resolve()
        candidate.relative_to(ASSET_DIR.resolve())
        if candidate.suffix.lower() not in AUDIO_EXTENSIONS or not candidate.is_file():
            return None
        return candidate
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
