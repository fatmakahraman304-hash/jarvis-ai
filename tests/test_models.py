"""Model seçimi testi: Gemini'de en yeni sohbet modeli (3.8) seçilir, aynı adlı tts/live sürümleri seçilmez,
kota/erişim hatasında aynı sağlayıcının sıradaki modeline geçilir, eski 2.x sabitlemeleri bir kez temizlenir.
Çalıştır: python tests/test_models.py"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_mdl_")
os.environ["GEMINI_API_KEY"] = "test"
for k in ("GEMINI_MODEL", "GROQ_API_KEY", "OPENROUTER_API_KEY", "XAI_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY", "CUSTOM_BASE_URL"):
    os.environ.pop(k, None)

from core import llm  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


AVAIL = ["gemini-2.5-flash", "gemini-3.8-flash-tts", "gemini-3.8-live", "gemini-3.8-flash-lite-tts", "gemini-embedding-001",
         "gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-nano-banana-2.1"]
llm.list_models = lambda pid, refresh=False: list(AVAIL) if pid == "gemini" else []
llm.configured = lambda pid: pid == "gemini"

print("MODELLER")
check("otomatik beyin = gemini-3.8-flash", llm.pick_model("gemini") == "gemini-3.8-flash", llm.pick_model("gemini"))
r = llm.ranked_models("gemini")
check("tts/live/embedding/görsel modeller listede yok", not any(x in m for m in r for x in ("tts", "live", "embedding", "banana")), r)
check("sıra: 3.8 → 3.6 → 3.5-lite → 2.5", r[:4] == ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"], r)
AVAIL.remove("gemini-3.8-flash")
check("3.8 hesapta yoksa 3.6'ya düşer (tts sürümüne değil)", llm.pick_model("gemini") == "gemini-3.6-flash", llm.pick_model("gemini"))
AVAIL.append("gemini-3.8-flash")
os.environ["GEMINI_MODEL"] = "gemini-3.6-flash"
check("elle seçilen model kullanılır", llm.pick_model("gemini") == "gemini-3.6-flash")
os.environ["GEMINI_MODEL"] = ""

seen = []


def fake_stream(pid, model, messages, tools=None, temperature=0.7, timeout=90):
    seen.append(model)
    if model == "gemini-3.8-flash":
        raise llm.ProviderError(pid, 429, "quota")
    yield ("text", "merhaba")
    yield ("final", {"content": "merhaba", "tool_calls": []})


llm.stream_chat = fake_stream
evs = list(llm.route(["gemini"], [{"role": "user", "content": "selam"}], None))
check("3.8 kotası dolunca 3.6 ile cevap verir", seen == ["gemini-3.8-flash", "gemini-3.6-flash"] and ("text", "merhaba") in evs, seen)

# eski sabitlemelerin temizlenmesi
from core import server  # noqa: E402
from core.config import load_settings, save_settings  # noqa: E402
save_settings({"personas": {"jarvis": {"providers": ["gemini"], "model": "gemini-2.5-flash"}, "friday": {"providers": ["gemini"], "model": "gemini-3.6-flash"}}})
envf = ROOT / ".env"
backup = envf.read_text(encoding="utf-8") if envf.exists() else None
try:
    envf.write_text((backup or "") + "\nGEMINI_MODEL=gemini-2.5-flash\n", encoding="utf-8")
    os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"
    server._migrate_old_models()
    st = load_settings()
    check("kişilikteki 2.5 sabitlemesi kaldırıldı", st["personas"]["jarvis"]["model"] == "")
    check("bilinçli 3.x seçimi korunur", st["personas"]["friday"]["model"] == "gemini-3.6-flash")
    check(".env'deki GEMINI_MODEL=2.5 kaldırıldı", "GEMINI_MODEL=gemini-2.5" not in envf.read_text(encoding="utf-8") and not os.environ.get("GEMINI_MODEL"))
    save_settings({"personas": {"jarvis": {"model": "gemini-2.5-flash"}}})
    server._migrate_old_models()
    check("geçiş yalnızca bir kez (sonra seçimine dokunmaz)", load_settings()["personas"]["jarvis"]["model"] == "gemini-2.5-flash")
finally:
    if backup is None:
        envf.unlink(missing_ok=True)
    else:
        envf.write_text(backup, encoding="utf-8")

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
