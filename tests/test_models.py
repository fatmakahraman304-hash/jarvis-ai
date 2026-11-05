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

check("kotası dolan 3.8 kenara alındı → sonraki mesaj doğrudan 3.6", llm.pick_model("gemini") == "gemini-3.6-flash")
llm._cooldown.clear(); seen.clear()


def daily_429(pid, model, messages, tools=None, temperature=0.7, timeout=90):
    seen.append(model)
    if model == "gemini-3.8-flash":
        raise llm.ProviderError(pid, 429, '{"error":{"details":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}')
    yield ("text", "ok")
    yield ("final", {"content": "ok", "tool_calls": []})


llm.stream_chat = daily_429
list(llm.route(["gemini"], [{"role": "user", "content": "a"}], None))
t = llm.cooling("gemini", "gemini-3.8-flash")
import time as _t  # noqa: E402
check("günlük kota dolunca yarın yenilenene kadar atlanır", t - _t.time() > 120 and t - _t.time() <= 86400 + 600)
seen.clear(); list(llm.route(["gemini"], [{"role": "user", "content": "b"}], None))
check("ikinci mesajda 3.8 hiç denenmez (boşuna bekleme yok)", seen == ["gemini-3.6-flash"], seen)
llm._cooldown.clear(); seen.clear()
list(llm.route(["gemini"], [{"role": "user", "content": "c"}], None, light=True))
check("arka plan işleri hafif ücretsiz modelle (3.5 Flash-Lite)", seen == ["gemini-3.5-flash-lite"], seen)
llm._cooldown.clear()

GROQ = ["llama-3.1-8b-instant", "whisper-large-v3", "meta-llama/llama-prompt-guard-2-86m", "openai/gpt-oss-safeguard-20b",
        "canopylabs/orpheus-v1-english", "llama-3.3-70b-versatile", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]
llm.list_models = lambda pid, refresh=False: list(AVAIL) if pid == "gemini" else (list(GROQ) if pid == "groq" else [])
check("Groq beyni = GPT-OSS 120B (en güçlü ücretsiz)", llm.pick_model("groq") == "openai/gpt-oss-120b", llm.pick_model("groq"))
rg = llm.ranked_models("groq")
check("Groq: whisper/guard/ses modelleri seçilmez", rg[:5] == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-8b-instant"] and len(rg) == 5, rg)
check("Groq arka plan işi = GPT-OSS 20B", llm.light_model("groq") == "openai/gpt-oss-20b")
f = llm.ThinkFilter()
check("Qwen'in <think> iç düşüncesi cevaba karışmaz", "".join(f.feed(x) for x in ["<thi", "nk>plan…</thi", "nk>\n\nTamam efendim."]) + f.flush() == "Tamam efendim.")

print("ANAHTAR SAĞLIĞI")
check("tırnak/boşluk/önek temizlenir", llm.clean_key(' "GEMINI_API_KEY=AIzaSyA1234567890abcdefghijklmnopqrstu " ') == "AIzaSyA1234567890abcdefghijklmnopqrstu")
os.environ["GEMINI_API_KEY"] = "AIzaYANLIS"
seen.clear()


def badkey(pid, model, messages, tools=None, temperature=0.7, timeout=90):
    seen.append(pid)
    if pid == "gemini":
        raise llm.ProviderError(pid, 400, '{"error":{"code":400,"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT"}}')
    yield ("text", "groq cevabı")
    yield ("final", {"content": "groq cevabı", "tool_calls": []})


llm.stream_chat = badkey
llm.configured = lambda pid: pid in ("gemini", "groq")
evs = list(llm.route(["gemini", "groq"], [{"role": "user", "content": "x"}], None))
check("geçersiz Gemini anahtarı → başka Gemini modeli denenmeden Groq cevap verir", seen == ["gemini", "groq"] and ("text", "groq cevabı") in evs, seen)
d = llm.key_bad("gemini")
check("anlaşılır teşhis (AIza / 39 karakter)", "geçersiz" in d and "uzunluğu 10" in d and "AIza" in d, d)
seen.clear(); list(llm.route(["gemini", "groq"], [{"role": "user", "content": "y"}], None))
check("sonraki mesajda bozuk anahtar hiç denenmez", seen == ["groq"], seen)
check("Ayarlar'da 'anahtar geçersiz' görünür", any(p["id"] == "gemini" and p["key_error"] for p in llm.status()))
llm.clear_key_state(); os.environ["GEMINI_API_KEY"] = "test"
llm.configured = lambda pid: pid == "gemini"

# eski sabitlemelerin temizlenmesi
from core import server  # noqa: E402
from core.config import load_settings, save_settings  # noqa: E402
save_settings({"personas": {"jarvis": {"providers": ["gemini"], "model": "gemini-2.5-flash"}, "friday": {"providers": ["gemini"], "model": "gemini-3.6-flash"},
                            "ultron": {"providers": ["groq"], "model": "llama-3.3-70b-versatile"}}})
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
    st2 = load_settings()
    check("Groq'taki eski llama-3.3 sabitlemesi de kaldırıldı", st2["personas"]["ultron"]["model"] == "")
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
