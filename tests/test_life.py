"""Toplantı, odak, günlük, bitki, haber sahneleri, nesne notları, oyun skorları (sahte model/haber).  python tests/test_life.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_life_")
from starlette.testclient import TestClient  # noqa: E402
from core import brain, server, tools  # noqa: E402
from core.skills import daily, life, scene  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


asked = []


def fake_ask(prompt, system="", persona_id=None, light=True):
    asked.append(prompt[:60])
    if "toplantının" in prompt:
        return json.dumps({"başlık": "Bütçe toplantısı", "özet": "Bütçe konuşuldu.", "kararlar": ["Reklam bütçesi artacak"],
                           "yapılacaklar": [{"iş": "Teklifi hazırla", "kim": "Ahmet", "tarih": "cuma"}], "açık_sorular": []})
    if "sahnelik" in prompt:
        return json.dumps({"giriş": "Bugün üç başlık var.", "sahneler": [{"başlık": "Faiz", "anlatım": "Merkez bankası faizi sabit tuttu.", "büyük": "%45", "etiket": "ekonomi", "kaynaklar": ["AA"]}], "kapanış": "Bu kadar."})
    return "Bu hafta yoğun ama iyi geçmiş."


brain.ask = fake_ask
c = TestClient(server.app)
print("YAŞAM")
r = c.post("/api/life/meeting_finish", json={"transcript": "Ahmet cuma günü teklifi hazırlayacak. Reklam bütçesi artırılsın dedik." * 2, "title": ""}).json()
check("toplantı → özet, kararlar, yapılacaklar; .md kaydı", r["başlık"] == "Bütçe toplantısı" and Path(r["dosya"]).exists() and "## Kararlar" in Path(r["dosya"]).read_text(encoding="utf-8"), r)
check("yapılacaklar listesine eklendi", r["eklenen_iş"] == 1 and "Teklifi hazırla" in str(tools.TOOLS["todo_list"][0]()))
check("kısa döküm reddedilir", "error" in c.post("/api/life/meeting_finish", json={"transcript": "kısa"}).json())
c.post("/api/life/focus_log", json={"minutes": 25, "task": "rapor", "done": True})
st = c.get("/api/life/focus_stats").json()
check("odak istatistiği", st["bugün_dk"] == 25 and st["bugün_oturum"] == 1, st)
check("odak modu komutu", tools.TOOLS["focus_mode"][0](50, "kod")["minutes"] == 50)
tools.TOOLS["journal_add"][0]("Bugün koşuya çıktım, iyi hissettim", "mutlu")
check("günlük yazılır/okunur", tools.TOOLS["journal_read"][0](7)[0]["ruh_hali"] == "mutlu")
check("günlük haftalık değerlendirme", "hafta" in tools.TOOLS["journal_summary"][0](7))
tools.TOOLS["plant_reminder"][0]("Monstera", 3)
d = life._load(); d["plants"][0]["last"] = time.time() - 4 * 86400; life._save(d)
notes = []
life.time.localtime = lambda *a: time.struct_time((2026, 11, 5, 12, 0, 0, 3, 309, 0))
life._last_tick[0] = 0; life.tick(lambda t, k="info": notes.append(t))
life._last_tick[0] = 0; life.tick(lambda t, k="info": notes.append(t))
check("sulama zamanı gelince (günde bir kez) hatırlatır", len(notes) == 1 and "Monstera" in notes[0], notes)
check("'suladım' → sayaç sıfırlanır", "sulandı" in tools.TOOLS["plant_watered"][0]("monstera") and tools.TOOLS["plant_list"][0]()[0]["sonraki"] > 2.9)
life.time.localtime = time.localtime
daily_news = [{"başlık": "Merkez Bankası faizi %45'te sabit tuttu", "kaynak": "AA", "tarih": "05 Nov"}]
daily.news = lambda topic="", country="TR", limit=10: daily_news
ns = tools.TOOLS["news_show"][0]()
check("'aydınlat beni' → sahneler (büyük sayı, kaynak)", ns["ui"] == "newsshow" and ns["sahneler"][0]["büyük"] == "%45" and ns["giriş"], ns)
check("model haberleri tekrar etmesin diye not", "TEK kısa cümle" in ns["not"])
print("NESNE NOTLARI")
check("not bırak", "Not buzdolabı" in tools.TOOLS["object_note"][0]("buzdolabına", "süt al") or "📌" in tools.TOOLS["object_note"][0]("buzdolabına", "yumurta al"))
scene.llm.vision = lambda *a, **k: '[{"ad": "Buzdolabı", "box": [100, 100, 400, 900]}, {"ad": "Masa", "box": [500, 600, 900, 900]}]'
rr = c.post("/api/scene/room", content=b"jpg").json()
fr = next(x for x in rr["nesneler"] if x["ad"] == "Buzdolabı")
check("taramada buzdolabı görülünce not gelir", [n["t"] for n in fr.get("notlar", [])] in (["süt al"], ["süt al", "yumurta al"], ["yumurta al"]) and "notlar" not in next(x for x in rr["nesneler"] if x["ad"] == "Masa"), rr)
check("not listesi / silme", isinstance(tools.TOOLS["object_note"][0]("buzdolabı", action="list"), list) and "silindi" in tools.TOOLS["object_note"][0]("buzdolabı", action="sil"))
g1 = c.post("/api/life/game_score", json={"game": "balloons", "score": 12}).json(); g2 = c.post("/api/life/game_score", json={"game": "balloons", "score": 8}).json()
check("oyun rekoru", g1["yeni_rekor"] and not g2["yeni_rekor"] and g2["rekor"] == 12)
check("komut grupları", all(g in tools.pick_groups(q) for q, g in [("toplantıyı kaydet", "life"), ("aydınlat beni", "life"), ("taş kağıt makas oynayalım", "life"), ("bitkimi kontrol et", "life"), ("buzdolabına not bırak", "scene")]))
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
