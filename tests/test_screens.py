"""Telefon ekranları (kayıt, komut kuyruğu, hedefleme, farklı videolar), arama, kilit araçları ve API.  python tests/test_screens.py"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_scr_")
from starlette.testclient import TestClient  # noqa: E402
from core import server, tools  # noqa: E402
from core.skills import screens as sc, media  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


check("telefon yokken anlaşılır yönerge", "rol=ekran" in sc.phone_screens()["not"])
check("telefon yokken arama bilgisayarda çalar", sc.call_me("Toplantın 10 dk sonra")["ui"] == "call")
sc.register("a1", "SALON")
sc.register("b2", "MUTFAK")
sc.register("c3", "YATAK")
check("3 telefon listede", len(sc.phone_screens()["telefonlar"]) == 3)
media.youtube_search = lambda q, recent=False, n=5: [{"id": ("x" * 10 + q[0])[:11], "title": "T-" + q, "channel": "K", "when": ""}]
r = sc.phone_video("alfa | beta | gama")
check("her telefona farklı video", len({x["video"] for x in r["oynatılıyor"]}) == 3, r)
q = sc.register("a1")
check("komut kuyruktan teslim edilir (video)", q and q[0]["type"] == "video" and q[0]["id"], q)
check("kuyruk boşalır", sc.register("a1") == [])
r = sc.phone_video("rick", "mutfak")
check("ada göre tek telefon", [x["telefon"] for x in r["oynatılıyor"]] == ["MUTFAK"], r)
check("olmayan telefon hata", "error" in sc.phone_video("x", "banyo"))
sc.phone_show("Yemek hazır!", "hepsi")
check("yazı hepsine gider", all(any(c["type"] == "show" for c in sc.register(i)) for i in ("a1", "c3")))
r = sc.call_me("Kalk efendim", "SALON")
check("JARVIS telefonu arar", r.get("çalan") == ["SALON"] and sc.register("a1")[0]["type"] == "ring", r)
check("animasyon adı tahmin edilir", sc.phone_anim("havai fişek", "YATAK")["animasyon"] == "fireworks")
check("kilit aracı", sc.system_lock() == {"ui": "lock", "on": True} and sc.system_lock("kapat")["on"] is False)
check("'beni ara' screens grubunu açar", "screens" in tools.pick_groups("beni ara"))
names = [s["function"]["name"] for s in tools.specs({"screens", "core"})]
check("araçlar kayıtlı", all(n in names for n in ("phone_video", "call_me", "system_lock", "voice_call")))
c = TestClient(server.app)
j = c.get("/api/screens/poll", params={"id": "zz9", "name": "TABLET", "state": ""}).json()
check("API poll kaydeder", j == {"cmds": []} and any(x["ad"] == "TABLET" for x in c.get("/api/screens/list").json()["telefonlar"]))
j = c.post("/api/screens/send", json={"type": "say", "text": "selam", "target": "TABLET"}).json()
check("API send", j.get("ok") and c.get("/api/screens/poll", params={"id": "zz9"}).json()["cmds"][0]["type"] == "say", j)
check("API geçersiz tür 400", c.post("/api/screens/send", json={"type": "rm"}).status_code == 400)
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
