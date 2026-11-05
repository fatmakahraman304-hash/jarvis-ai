"""Oda tarama / nesne hafızası / belge / çizim / avuç HUD uç noktaları (sahte model).  python tests/test_scene.py"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_scene_")
from starlette.testclient import TestClient  # noqa: E402
from core import server, tools  # noqa: E402
from core.skills import scene  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


calls = []


def fake_vision(prompt, img, mime="image/png", system="", light=False):
    calls.append((prompt[:40], light))
    if "oda/ortam" in prompt:
        return 'İşte: [{"ad": "Kumanda", "tür": "elektronik", "box": [700, 600, 800, 700], "not": "siyah"}, {"ad": "Kanepe", "box": [0, 300, 600, 1000]}, {"ad": "bozuk"}, {"ad": "Sıfır", "box": [5, 5, 5, 5]}]'
    if "Bu nesne nedir" in prompt:
        return '{"ad": "Kumanda", "ne": "TV kumandası.", "arama": "tv kumandası"}'
    if "çizim" in prompt:
        return "Bir kalp çizmişsiniz!"
    return "METİN: Fatura 120 TL"


scene.llm.vision = fake_vision
c = TestClient(server.app)
print("SAHNE")
r = c.post("/api/scene/room?location=salon", content=b"\xff\xd8jpg").json()
check("oda taraması: geçerli nesneler kutularıyla (bozuk/boş kutular elenir)", [x["ad"] for x in r["nesneler"]] == ["Kumanda", "Kanepe"] and r["nesneler"][0]["box"] == [0.7, 0.6, 0.8, 0.7], r)
check("oda taraması hafif modelle", calls[-1][1] is True)
w = tools.TOOLS["where_is"][0]("kumandayı")
check("nesne hafızası: 'kumandayı nerede bıraktım' → salon, sağ alt", w.get("nesne") == "Kumanda" and "salon" in w["son_görüldüğü"] and "sağ alt" in w["son_görüldüğü"] and w["ne_zaman"] == "az önce", w)
check("bilinmeyen nesne dürüst", "bulunamadı" in tools.TOOLS["where_is"][0]("gözlük"))
o = c.post("/api/scene/object?name=Kumanda", content=b"x").json()
check("tıklanan nesne → hologram bilgi kartı", o.get("ne") == "TV kumandası." and o.get("arama"), o)
q = c.post("/api/scene/object?name=Kumanda&question=nasıl%20temizlenir", content=b"x").json()
check("nesneye soru", "cevap" in q)
d = c.post("/api/scene/doc?mode=text", content=b"x").json()
check("belge: yazı çıkar", "Fatura" in d["metin"])
s = c.post("/api/scene/save", json={"text": "deneme metni", "name": "fatura"}).json()
check("belge kaydedilir", s.get("dosya", "").endswith("fatura.txt") and Path(s["dosya"]).read_text(encoding="utf-8") == "deneme metni", s)
check("çizim: ne çizdim", "kalp" in c.post("/api/scene/drawing", content=b"png").json()["cevap"])
check("avuç HUD verisi", "sistem" in c.get("/api/scene/palm").json())
f = tools.TOOLS["find_object"][0]("kumanda")
check("'kumandayı bul' → canlı arama + hafıza", f["ui"] == "scan" and f["mode"] == "find" and f["hafıza"].get("nesne") == "Kumanda")
check("sesli komutlar", tools.TOOLS["body_mode"][0]("şınav", 10)["kind"] == "pushup" and tools.TOOLS["ar_extra"][0]("çizim")["extra"] == "draw" and tools.TOOLS["doc_scan"][0]("özet")["doc"] == "summary")
check("'odayı tara' doğru araç grubunu açar", "scene" in tools.pick_groups("odayı tara") and "scene" in tools.pick_groups("kumandayı nerede bıraktım") and "scene" in tools.pick_groups("10 squat say"))
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
