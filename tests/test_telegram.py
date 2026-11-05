"""Telegram köprüsü testi (gerçek Telegram'a bağlanmaz): panel düğmeleri, uyutma onayı, yetkisiz düğme,
ekran görüntüsü, sesli cevap ve /ses kalıcılığı. Çalıştır: python tests/test_telegram.py"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_tg_")
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
os.environ["TELEGRAM_ALLOWED_IDS"] = "111"

from core import telegram_bot as tg, tools, voice  # noqa: E402
from core.config import load_settings, save_settings  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


calls, files, did = [], [], []


class Stop(BaseException):
    pass


UPDATES = []


def fake_call(method, params=None, timeout=40):
    calls.append((method, params or {}))
    if method == "getUpdates":
        if not UPDATES:
            raise Stop()
        return {"ok": True, "result": [UPDATES.pop(0)]}
    return {"ok": True, "result": {}}


tg._call = fake_call
tg._send_file = lambda method, field, chat_id, data, filename, mime, caption="": files.append((method, field, chat_id, len(data), caption))
tg.screenshot_jpeg = lambda max_w=2560: b"\xff\xd8JPEGDATA\xff\xd9"
tools.lock_pc = lambda: did.append("lock") or "Bilgisayar kilitlendi."
tools.power = lambda a: did.append("power:" + a) or "ok"
tools.media_control = lambda a, steps=5: did.append("media:" + a) or "Tamam: mute"
voice.available = lambda: True


async def fake_synth(text, pid, *a, **k):
    did.append("tts:" + text[:20])
    return b"ID3fake-mp3"
voice.synthesize = fake_synth


def texts():
    return [p.get("text", "") for m, p in calls if m in ("sendMessage", "editMessageText")]


print("TELEGRAM")
tg._handle(111, "/panel")
kb = calls[-1][1].get("reply_markup", {}).get("inline_keyboard", [])
datas = [b["callback_data"] for row in kb for b in row]
check("/panel düğmeli klavye gönderir", calls[-1][0] == "sendMessage" and {"lock", "sleep", "screen", "status", "mute", "brief", "stop"} <= set(datas), datas)

calls.clear()
tg._on_button(111, 55, "lock")
check("🔒 Kilitle bilgisayarı kilitler", did[-1] == "lock" and any("kilitlendi" in t for t in texts()))

calls.clear(); did.clear()
tg._on_button(111, 55, "sleep")
check("😴 Uyut hemen uyutmaz, onay sorar", "power:sleep" not in did and calls[-1][0] == "editMessageText"
      and [b["callback_data"] for b in calls[-1][1]["reply_markup"]["inline_keyboard"][0]] == ["sleep_yes", "sleep_no"])
tg._on_button(111, 55, "sleep_no")
time.sleep(2.3)
check("Vazgeç → uyutulmaz", "power:sleep" not in did)
tg._on_button(111, 55, "sleep_yes")
time.sleep(2.3)
check("Evet → uyutulur", "power:sleep" in did)

files.clear()
tg._on_button(111, 55, "screen")
check("📸 Ekran fotoğraf olarak gelir", files and files[-1][0] == "sendPhoto" and files[-1][1] == "photo" and files[-1][2] == 111)
files.clear()
tg._handle(111, "/ekran")
check("/ekran komutu da çalışır", files and files[-1][0] == "sendPhoto")
save_settings({"allow_remote_screen": False}); files.clear(); calls.clear()
tg._handle(111, "/ekran")
check("izin kapalıyken ekran gönderilmez", not files and any("izni kapalı" in t for t in texts()))
save_settings({"allow_remote_screen": True}); files.clear()
r = tools.TOOLS["screenshot_to_phone"][0]()
check("screenshot_to_phone aracı izinli hesaba yollar", "gönderildi" in r and files and files[-1][2] == "111", r)

tg._on_button(111, 55, "mute")
check("🔇 sesi kapatır", "media:mute" in did)

# yetkisiz kullanıcı düğmeye basarsa hiçbir şey olmaz
did.clear(); calls.clear()
UPDATES[:] = [{"update_id": 1, "callback_query": {"id": "q1", "from": {"id": 999}, "data": "lock", "message": {"message_id": 5, "chat": {"id": 999}}}},
              {"update_id": 2, "callback_query": {"id": "q2", "from": {"id": 111}, "data": "lock", "message": {"message_id": 6, "chat": {"id": 111}}}}]
try:
    tg._loop()
except Stop:
    pass
time.sleep(0.5)
ans = [p for m, p in calls if m == "answerCallbackQuery"]
check("menü komutları telefona tanıtıldı", any(m == "setMyCommands" for m, _ in calls))
check("her düğmeye cevap verilir (dönen saat durur)", [a["callback_query_id"] for a in ans] == ["q1", "q2"])
check("yetkisiz düğme reddedilir, yetkili çalışır", did.count("lock") == 1 and ans[0]["text"] == "Yetkin yok.")

# sesli cevap: /ses kalıcı + yazılı mesaja sesli cevap
tg._voice_on.clear(); save_settings({"telegram_voice": {}})
tg._handle(111, "/ses")
check("/ses açar ve ayara kaydeder", load_settings().get("telegram_voice", {}).get("111") is True)
tg._voice_on.clear()
check("yeniden başlayınca da açık kalır", tg.voice_enabled(111) is True)
files.clear(); did.clear()
check("sesli cevap 'sesli mesaj' olarak gider", tg.speak_to(111, "**Merhaba** efendim", "jarvis") and files and files[-1][0] == "sendVoice" and "tts:Merhaba efendim" in did)
orig = tg._send_file


def flaky(method, *a, **k):
    if method == "sendVoice":
        raise RuntimeError("voice desteklenmedi")
    files.append((method,) + a[:1])
tg._send_file = flaky; files.clear()
tg.speak_to(111, "Deneme", "jarvis")
check("sesli mesaj olmazsa mp3 olarak gönderilir", files and files[-1][0] == "sendAudio")
tg._send_file = orig
tg._handle(111, "/ses")
check("/ses ikinci kez kapatır", tg.voice_enabled(111) is False)

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
