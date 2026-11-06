"""Ayarlar: .env (API anahtarları) + data/settings.json (arayüzden değişen ayarlar)."""
import json
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("JARVIS_DATA") or (ROOT / "data"))
WEB = ROOT / "web"
DATA.mkdir(exist_ok=True)
SETTINGS_FILE = DATA / "settings.json"

VERSION = "4.6.44"


def _load_env():
    env_file = ROOT / ".env"
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_file)
        return
    except Exception:
        pass
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = re.split(r"\s+#", v, 1)[0] if not v.strip().startswith(("'", '"')) else v
            v = v.strip().strip('"').strip("'")
            if v or k.strip() not in os.environ:
                os.environ[k.strip()] = v


_load_env()


def env(name, default=""):
    return os.environ.get(name, default).strip()


DEFAULT_SETTINGS = {
    "persona": "jarvis",
    "only_gemini": True,         # tek beyin: yalnızca Google Gemini (diğer anahtarlar durur ama kullanılmaz)
    "visual": "reactor",         # reactor | wave | sphere | face
    "response_length": "normal",
    "theme": "dark",
    "voice_enabled": True,
    "voice_lang": "auto",        # auto | tr | en
    "wake_word": True,
    "effects": True,
    "auto_control": False,       # masaüstünü tamamen otonom kullanmak için isteğe bağlı
    "routine_browser_auto": True, # güvenli ve sıradan tarayıcı adımlarında onay isteme
    "email_watch": True,         # önemli yeni e-postayı bildir
    "meeting_alerts": True,      # toplantıdan 10 dk önce bildir
    "city": "Istanbul",
    "voice_id": False,           # konuşanı sesinden tanı
    "voice_lock": False,         # sadece tanıdığı seslere cevap ver
    "track_usage": True,         # uygulama kullanım süreleri (sadece yerel)
    "clipboard_history": True,   # pano geçmişi (sadece yerel)
    "guest_mode": False,         # misafir modu: kişisel veri ve kritik işlem yok
    "allow_remote_commands": False,  # ağdaki diğer JARVIS'lerden gelen komutları kabul et
    "allow_remote_camera": False,  # telefondan/Telegram'dan kamera görüntüsü
    "robot_port": "", "robot_url": "", "robot_baud": 115200,
    "personas": {
        # her kişilik için sağlayıcı sırası; ilk çalışan kullanılır, diğerleri yedek
        "jarvis": {"providers": ["gemini", "groq", "openrouter", "mistral", "cerebras", "xai", "ollama"], "model": ""},
        "friday": {"providers": ["groq", "gemini", "cerebras", "openrouter", "mistral", "xai", "ollama"], "model": ""},
    },
    "live_voice_names": {"jarvis": "Charon", "friday": "Aoede"},
    "voice": {
        "jarvis": {"rate": 0, "pitch": 0},
        "friday": {"rate": 0, "pitch": 0},
    },
}

_lock = threading.Lock()


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings():
    with _lock:
        data = {}
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        merged = _merge(DEFAULT_SETTINGS, data)
        changed = False
        for key in ("personas", "live_voice_names", "voice", "voice_pick", "voice_fx", "original_voice"):
            values = merged.get(key)
            if isinstance(values, dict) and "ultron" in values:
                values.pop("ultron", None)
                changed = True
        if merged.get("persona") not in ("jarvis", "friday"):
            merged["persona"] = "jarvis"
            changed = True
        if not data.get("always_listen_migrated"):
            merged["wake_word"] = True
            merged["always_listen_migrated"] = True
            changed = True
        if not data.get("continuous_voice_v2"):
            merged["wake_word"] = True
            merged["voice_enabled"] = True
            merged["continuous_voice_v2"] = True
            changed = True
        if changed and SETTINGS_FILE.exists():
            SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged


def save_settings(patch):
    current = load_settings()
    new = _merge(current, patch or {})
    for key in ("personas", "live_voice_names", "voice", "voice_pick", "voice_fx", "original_voice"):
        values = new.get(key)
        if isinstance(values, dict):
            values.pop("ultron", None)
    if new.get("persona") not in ("jarvis", "friday"):
        new["persona"] = "jarvis"
    with _lock:
        SETTINGS_FILE.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    return new
