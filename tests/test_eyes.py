"""Telefon kamerası + kitaplık + YouTube testi (internet ve gerçek model olmadan).
Çalıştır: python tests/test_eyes.py"""
import io
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_eyes_")
from starlette.testclient import TestClient  # noqa: E402

from core import llm, server, tools  # noqa: E402
from core.skills import cams, library, LOAD_ERRORS  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


c = TestClient(server.app)
check("araç adları çakışmıyor", not [k for k in LOAD_ERRORS if k.startswith("dup:")], LOAD_ERRORS)

print("TELEFON KAMERASI")
JPG = b"\xff\xd8\xff\xe0" + b"0" * 5000 + b"\xff\xd9"
r = c.post("/api/cams?id=cam1&name=CAM-01&loc=Mutfak&motion=0&w=640&h=360", content=JPG, headers={"Content-Type": "image/jpeg"}).json()
check("telefon kare gönderir", r.get("hd") is False and "viewers" in r, r)
lst = c.get("/api/cams").json()["cams"]
check("kamera listede çevrimiçi", lst and lst[0]["online"] and lst[0]["loc"] == "Mutfak", lst)
check("son kare izlenebilir", c.get("/api/cams/cam1.jpg?viewer=v1").content == JPG)
check("izleyici sayısı telefona döner", c.post("/api/cams?id=cam1", content=JPG).json()["viewers"] == 1)
seen = {}


def fake_vision(prompt, img, mime="image/png", system="", light=False):
    seen.update(prompt=prompt, img=img, light=light)
    return "Tezgâhta bir fincan ve kahve makinesi var."


llm.vision = fake_vision


def phone():  # JARVIS bakmak isteyince telefon hemen yeni (HD) kare yollar
    time.sleep(0.4)
    cams.put_frame("cam1", JPG + b"HD", "CAM-01", "Mutfak")


threading.Thread(target=phone, daemon=True).start()
ans = tools.TOOLS["room_camera_look"][0]("Kahve makinesinin önünde fincan var mı?", "mutfakta")
check("'mutfakta ne var' → doğru kameradan taze kare", "fincan" in ans and seen["img"].endswith(b"HD") and "Kişileri adıyla" in seen["prompt"], ans)
check("olmayan konum anlaşılır cevap", "kamera yok" in tools.TOOLS["room_camera_look"][0]("ne var", "garaj"))
sent = []
from core import telegram_bot  # noqa: E402
telegram_bot._send_file = lambda *a, **k: sent.append(a)
telegram_bot._allowed = lambda: ["111"]
os.environ["TELEGRAM_BOT_TOKEN"] = "1:x"
tools.TOOLS["security_mode"][0](True)
cams.put_frame("cam1", JPG, motion=True); time.sleep(0.5)
cams.put_frame("cam1", JPG, motion=True); time.sleep(0.3)
check("güvenlik modu: hareket → Telegram'a fotoğraf (dakikada en fazla 1)", len(sent) == 1 and sent[0][0] == "sendPhoto", sent)
from core import memory  # noqa: E402
check("güvenlik bildirimi düştü", any("Hareket algılandı" in n["text"] for n in memory.notifications_since(0)))
tools.TOOLS["security_mode"][0](False)

print("KİTAPLIK")
from PIL import Image  # noqa: E402
buf = io.BytesIO(); Image.new("RGB", (1200, 600), (90, 60, 40)).save(buf, "JPEG"); SHELF = buf.getvalue()
calls = []


def shelf_vision(prompt, img, mime="image/png", system="", light=False):
    calls.append(light)
    if len(calls) % 2:
        return 'Sonuç:\n[{"title": "Mülksüzler", "author": "Ursula K. Le Guin", "box": [100, 100, 200, 900]}, {"title": "", "author": "", "box": [600, 100, 680, 900]}]'
    return '[{"title": "Davranış", "author": "Robert Sapolsky", "box": [300, 50, 400, 950]}, {"title": "Mülksüzler", "author": "", "box": [90, 100, 210, 900]}]'


library.llm.vision = shelf_vision
r = c.post("/api/library/scan?w=1200&h=600", content=SHELF).json()
check("raf taraması: parçalara bölünür, hafif modelle okunur", len(calls) == 6 and all(calls), calls)
d = c.get("/api/library").json()
titles = sorted(b["title"] for b in d["books"] if b["title"])
check("aynı kitap parçalar arasında birleşir, belirsiz sırt adsız kalır", titles == ["Davranış", "Mülksüzler"] and any(not b["title"] for b in d["books"]), (titles, r))
check("raf bölgesi kaydedildi (sonraki tarama odaklanır)", len(d["shelf"].get("region", [])) == 4)
check("kutular tam görüntüye göre 0-1", all(0 <= v <= 1 for b in d["books"] for v in (b["box"] or [])))
nb_json = json.dumps({"bilinen": True, "ozet": "Anarres ve Urras.", "ana_fikirler": ["özgürlük"], "benzer": ["Davranış", "Uydurma Kitap"]})
from core import brain  # noqa: E402
brain.ask = lambda *a, **k: nb_json
library._cover = lambda *a: "https://covers.openlibrary.org/b/id/1-M.jpg"
f = tools.TOOLS["book_fill"][0]("Mülksüzler")
check("kitap defteri dolar; 'benzer' yalnızca kendi rafından", f["defter"]["benzer"] == ["Davranış"] and f["kapak"].startswith("https://covers"), f)
brain.ask = lambda *a, **k: '{"bilinen": false}'
f2 = tools.TOOLS["book_fill"][0]("Davranış", True)
check("tanımadığı kitapta uydurmaz", "uydurulmadı" in str(f2["defter"]))
tools.TOOLS["book_update"][0]("Mülksüzler", note="Anarres bölümü çok iyi", page=120)
tools.TOOLS["book_update"][0]("Tahıla Karşı", status="bitirdim")
lst = tools.TOOLS["book_list"][0]()
m = next(x for x in lst if x["ad"] == "Mülksüzler")
check("not + sayfa → okunuyor; olmayan kitap 'bitirdim' ile eklenir", m["sayfa"] == 120 and m["durum"] == "okunuyor" and m["not_sayısı"] == 1 and any(x["ad"] == "Tahıla Karşı" and x["durum"] == "bitti" for x in lst), lst)
sug = tools.TOOLS["book_suggest"][0]()
check("öneri yalnızca kendi rafından, bitenler hariç", all(x["ad"] != "Tahıla Karşı" for x in sug["aday_kitaplar"]))
unnamed = next(b for b in c.get("/api/library").json()["books"] if not b["title"])
c.post("/api/library/book", json={"id": unnamed["id"], "title": "Oblomov"})
calls.clear()
c.post("/api/library/scan?w=1200&h=600", content=SHELF)
d = c.get("/api/library").json()
check("elle verilen ad yeniden taramada ezilmez, notlar korunur", any(b["title"] == "Oblomov" for b in d["books"]) and any(b["title"] == "Mülksüzler" and b["notes"] for b in d["books"]))
check("sesli komut araçları var", all(t in tools.TOOLS for t in ("shelf_scan", "book_name_open", "book_add")))

print("YOUTUBE")
from core.skills import media  # noqa: E402
page = ('"videoRenderer":{"videoId":"abcDEF12345","title":{"runs":[{"text":"Fenerbahçe 2-1 | Maç Özeti"}]},"ownerText":{"runs":[{"text":"beIN SPORTS"}]},'
        '"publishedTimeText":{"simpleText":"1 gün önce"}')
urls = []
media._http_get = lambda url, timeout=12: (urls.append(url), page)[1]
v = tools.TOOLS["youtube_play"][0]("fenerbahçe maç özeti")
check("maç özeti JARVIS içinde açılır, en yeni sıralama", v["ui"] == "video" and v["id"] == "abcDEF12345" and "sp=CAI" in urls[-1], (v, urls))

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
