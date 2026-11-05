"""3D dünya, bilim, kontrol, günlük hayat ve proje araçları testi (internet ve gerçek cihaz gerektirmez).
Çalıştır: python tests/test_more.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis_more_")
HOME = Path(tempfile.mkdtemp(prefix="jarvis_home_"))
os.environ["HOME"] = str(HOME)
os.environ["USERPROFILE"] = str(HOME)

from core import tools  # noqa: E402
from core.skills import LOAD_ERRORS, control, daily, geo, holo  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


print("YÜKLEME")
check("modüller hatasız", not LOAD_ERRORS, LOAD_ERRORS)
check("200+ araç", len(tools.TOOLS) >= 200, len(tools.TOOLS))
bad = [n for n, (f, s, c) in tools.TOOLS.items() if not (callable(f) and s.get("parameters", {}).get("type") == "object")]
check("tüm araç şemaları geçerli", not bad, bad)
names = list(tools.TOOLS)
check("araç adları benzersiz ve geçerli", len(names) == len(set(names)) and all(n.replace("_", "").isalnum() for n in names))

print("COĞRAFYA")
check("ülke bul (Türkçe/İngilizce/kısaltma)", geo.find_country("almanya")["iso"] == "DEU" and geo.find_country("Germany")["iso"] == "DEU" and geo.find_country("abd")["iso"] == "USA")
i = geo.country_info("Japonya")
check("ülke bilgisi + başkent", i["başkent"] == "Tokyo" and i["nüfus"] > 100e6)
r = geo.rank_countries("yüzölçümü", 1)
check("en büyük ülke Rusya", r[0]["ülke"] in ("Rusya", "Rusya Federasyonu"), r)
check("mesafe İstanbul–Ankara ~350 km", 330 < geo.haversine((41.01, 28.97), (39.93, 32.86)) < 370)
gs = geo.globe_show("Fransa")
check("küre komutu (ülkeye uç)", gs["ui"] == "globe_fly" and gs["bilgi"]["ülke"] == "Fransa")
check("şehre uç (yerel veri)", geo.globe_show("Paris")["ui"] == "globe_fly")
check("katman komutu (Türkçe)", geo.globe_layer("uçuş")["layer"] == "flights" and geo.globe_layer("depremler")["layer"] == "quakes", geo.globe_layer("depremler"))
check("gemi rotaları", len(geo.ships()) >= 5)

print("BİLİM")
sdf = """water
  test

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.9572    0.0000    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0
   -0.2400    0.9266    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
M  END
"""
m = holo.parse_sdf(sdf, "water")
check("molekül dosyası okuma (H2O)", m["formül"] == "H2O" and len(m["bağlar"]) == 2, m["formül"])
c = holo.circuit_solve(12, [100, 200], "series")
check("seri devre (Ohm)", c["toplam_direnç_ohm"] == 300 and abs(c["toplam_akım_mA"] - 40) < 0.01)
p = holo.circuit_solve(10, [100, 100], "parallel")
check("paralel devre", p["toplam_direnç_ohm"] == 50 and abs(p["toplam_akım_mA"] - 200) < 0.01)
check("simülasyon komutu", holo.sim_show("güneş sistemi")["kind"] == "solar" and holo.sim_show("atom", '{"element":"Fe"}')["params"]["element"] == "Fe")
check("tasarım komutu", holo.holo_design("araba", '{"type":"sport"}')["kind"] == "car")
check("özel 3D sahne doğrulama", "JSON" in str(holo.holo_scene("x", "bozuk")) and holo.holo_scene("x", '[{"type":"box"}]')["count"] == 1)

print("GERİ ALMA")
d = HOME / "test"
d.mkdir()
f = d / "a.txt"
f.write_text("eski", encoding="utf-8")
tools.write_file(str(f), "yeni")
check("üzerine yazma", f.read_text(encoding="utf-8") == "yeni")
control.undo_last(1)
check("yazma geri alındı", f.read_text(encoding="utf-8") == "eski")
tools.move_file(str(f), str(d / "b.txt"))
control.undo_last(1)
check("taşıma geri alındı", f.exists() and not (d / "b.txt").exists())
tools.delete_file(str(f))
check("silme çöp kutusuna", not f.exists())
control.undo_last(1)
check("silme geri alındı", f.exists() and f.read_text(encoding="utf-8") == "eski")
for n in ("x.jpg", "y.pdf", "z.mp3"):
    (d / n).write_text("1")
tools.TOOLS["organize_folder"][0](str(d), False)
check("klasör düzenlendi", (d / "Resimler" / "x.jpg").exists())
control.undo_last(1)
check("klasör düzeni geri alındı", (d / "x.jpg").exists() and (d / "y.pdf").exists())
check("geçmiş (4 işlem)", len(control.undo_history()) >= 4)

print("ACİL DURDURMA / MİSAFİR")
from core import brain, memory  # noqa: E402
from core.skills import automation  # noqa: E402
automation.schedule_task("deneme", "interval", every_minutes=5)
brain._pending["abc"] = {"id": "abc", "name": "delete_file", "args": {}, "persona": "jarvis", "session": "x", "source": "web", "ts": 0}
control.emergency_stop("test")
check("acil durdurma: görevler durdu, bekleyenler iptal", control.ESTOP.is_set() and not brain.pending_list() and not memory._q("SELECT id FROM tasks WHERE enabled=1"))
fired = []
automation.tick(lambda t, k="i": fired.append(t))
check("acil durumda otomasyon çalışmaz", not fired)
control.emergency_reset()
check("acil durum kaldırıldı", not control.ESTOP.is_set())
evs = list(brain.chat("merhaba", "jarvis", "g", "web", guest=True))
check("misafir modu çalışır (model yoksa hata mesajı)", evs[-1]["type"] == "done")
groups = tools.pick_groups("gmail şifre")
check("misafirde kişisel gruplar kapalı", not ((groups - brain.GUEST_BLOCKED) & {"google", "vault"}))

print("AĞ")
import subprocess as sp  # noqa: E402


class R:
    stdout = "Reply from 8.8.8.8: bytes=32 time=21ms TTL=117\nReply from 8.8.8.8: bytes=32 time=25ms TTL=117\nRequest timed out.\nReply from 8.8.8.8: bytes=32 time<1ms TTL=117"


orig = sp.run
control.subprocess.run = lambda *a, **k: R()
pr = control.ping_test("8.8.8.8", 4)
control.subprocess.run = orig
check("ping çözümleme (kayıp %25)", pr["alınan"] == 3 and pr["kayıp_%"] == 25 and pr["maks_ms"] == 25, pr)

print("GÜNLÜK")
r = daily.set_alarm("07:30", "Uyan", "weekdays")
check("alarm kuruldu", "kuruldu" in r and daily.list_alarms()[0]["tekrar"] == "weekdays")
memory._q("UPDATE alarms SET at=?", (time.time() - 1,), commit=True)
rang = []
daily.alarm_tick(lambda t, k="i": rang.append((t, k)))
check("alarm çaldı ve tekrar kuruldu", rang and rang[0][1] == "alarm" and daily.list_alarms() != "Kurulu alarm yok.")
daily.note_add("Toplantıda bütçe konuşulacak", tags="iş")
check("not ara", daily.note_search("bütçe")[0]["etiket"] == "iş")
daily.shopping_add("2 kg elma, süt; 3 adet yumurta")
lst = daily.shopping_list()
check("alışveriş listesi (miktarlı)", [x["ürün"] for x in lst] == ["2 kg elma", "süt", "3 adet yumurta"], lst)
daily.shopping_update("süt")
check("alındı işaretle", len(daily.shopping_list()) == 2)
xml = '<rss><channel><item><title>Başlık 1 - Kaynak</title><link>https://x/1</link><pubDate>Wed, 04 Nov 2026 10:00:00 GMT</pubDate><source url="x">Kaynak A</source></item></channel></rss>'
daily._http_get = lambda url, timeout=12: xml
n = daily.news("ekonomi")
check("haber çözümleme", n[0]["kaynak"] == "Kaynak A" and n[0]["başlık"].startswith("Başlık 1"))

print("PROJE MERKEZİ")
pj = daily.create_project("Hesap Makinesi", json.dumps({
    "hesap.py": "def topla(a, b):\n    return a + b\n",
    "test_hesap.py": "import unittest\nfrom hesap import topla\n\nclass T(unittest.TestCase):\n    def test_topla(self):\n        self.assertEqual(topla(2, 3), 5)\n",
}))
check("proje oluşturuldu", Path(pj["proje"], "hesap.py").exists() and "test_hesap.py" in pj["dosyalar"])
rr = daily.run_project("Hesap_Makinesi")
check("testleri çalıştırdı ve geçti", rr["başarılı"], rr)
check("dışarı yazma engeli", "../kotu.py" not in daily.create_project("X", json.dumps({"../kotu.py": "x"}))["dosyalar"])

print("UZAY (bilinen gerçek olaylarla karşılaştırma)")
import datetime as dt  # noqa: E402
import math  # noqa: E402
from core.skills import space  # noqa: E402
Ut = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)


def hl(n, t):
    x, y, z = space.helio(n, space.jd(Ut(t)))
    return math.degrees(math.atan2(y, x)) % 360


check("Mars karşı konumu 16.01.2025 (boylam farkı < 0,5°)", abs(hl("Dünya", "2025-01-16 02:00") - hl("Mars", "2025-01-16 02:00")) < 0.5)
check("Jüpiter karşı konumu 07.12.2024", abs(hl("Dünya", "2024-12-07 21:00") - hl("Jüpiter", "2024-12-07 21:00")) < 0.5)
x, y, z = space.helio("Dünya", space.jd(Ut("2025-01-04 13:00")))
check("Dünya günberi uzaklığı 0,9833 AU", abs(math.sqrt(x * x + y * y + z * z) - 0.98333) < 0.0005)
check("Dolunay 13.01.2025", space.moon_phase(space.jd(Ut("2025-01-13 22:27")))["evre"] == "Dolunay")
check("Yeni Ay 29.01.2025", space.moon_phase(space.jd(Ut("2025-01-29 12:36")))["evre"] == "Yeni Ay")
ra, dec, _ = space.geo_radec("Güneş", space.jd(Ut("2025-03-20 09:01")))
check("Ekinoksta Güneş ekvatorda (dec≈0)", abs(dec) < 0.3)
check("Kutup Yıldızı yüksekliği ≈ enlem (İstanbul)", abs(space.altaz(37.95, 89.264, 41.01, 28.97, space.jd(Ut("2025-06-01 21:00")))[0] - 41) < 1.2)
pos = space.sat_position({"ad": "ISS", "id": 1, "epoch": "2025-06-01T12:00:00", "n": 15.5, "e": 0.0004, "i": 51.64, "raan": 100, "argp": 90, "M": 0}, Ut("2025-06-01 12:30"))
check("ISS yüksekliği ~420 km, hız ~27.600 km/sa", 400 < pos["yükseklik_km"] < 430 and 27000 < pos["hız_kmh"] < 28000 and abs(pos["lat"]) <= 51.7, pos)
check("ISS'in altındaki ülke bulunur", isinstance(space._country_at(39.0, 35.0), str) and space._country_at(39.0, 35.0) == "Türkiye")

print("CANLI DÜNYA TAKİBİ")
import socket as _so  # noqa: E402
import struct as _st  # noqa: E402
from core.skills import worldwatch as ww  # noqa: E402
a, b = _so.socketpair()
ws = ww._WS.__new__(ww._WS)
ws.s, ws.buf = a, b""
ws.send('{"APIKey":"x"}')
raw = b.recv(1024)
L = raw[1] & 0x7F
mask, payload = raw[2:6], raw[6:6 + L]
check("websocket gönderim (maskeli çerçeve)", raw[0] == 0x81 and raw[1] & 0x80 and bytes(x ^ mask[i % 4] for i, x in enumerate(payload)) == b'{"APIKey":"x"}')
big = json.dumps({"MetaData": {"MMSI": 1, "ShipName": "GEMİ", "Latitude": 41.0, "Longitude": 29.0}, "Message": {"PositionReport": {"Sog": 9.5}}, "pad": "x" * 300}).encode()
b.sendall(bytes([0x01, 126]) + _st.pack(">H", 100) + big[:100] + bytes([0x80, 126]) + _st.pack(">H", len(big) - 100) + big[100:])
m = json.loads(ws.recv())
check("websocket alım (parçalı + 16 bit uzunluk)", m["MetaData"]["ShipName"] == "GEMİ")
a.close(); b.close()
sample = {"events": [{"title": "Hurricane X", "categories": [{"id": "severeStorms"}], "sources": [{"url": "https://x"}],
                      "geometry": [{"date": "2026-11-01T00:00:00Z", "type": "Point", "coordinates": [-70, 20], "magnitudeValue": 80, "magnitudeUnit": "kts"},
                                   {"date": "2026-11-02T00:00:00Z", "type": "Point", "coordinates": [-72, 22]}]},
                     {"title": "Fire Y", "categories": [{"id": "wildfires"}], "geometry": [{"date": "2026-11-03", "type": "Polygon", "coordinates": [[[10, 40], [12, 40], [12, 42], [10, 42]]]}]}]}
ww._http_get = lambda url, timeout=12: json.dumps(sample)
ev = ww.eonet(30)
check("EONET: fırtına rotası + poligon merkezi", ev[0]["tür_tr"] == "Şiddetli fırtına" and len(ev[0]["iz"]) == 2 and ev[1]["son"][:2] == [41.0, 11.0], ev[1]["son"])
r = ww.world_events("kasırga")
check("Türkçe olay türü → kategori", r["category"] == "severeStorms")
os.environ["FIRMS_MAP_KEY"] = "k"
ww._http_get = lambda url, timeout=12: "latitude,longitude,bright_ti4,frp,acq_date\n38.5,27.1,330,12.5,2026-11-04\n-10,140,320,3,2026-11-04\n"
check("FIRMS yangın CSV", ww.firms(1) == [[38.5, 27.1, 12.5], [-10.0, 140.0, 3.0]])
ww._cache.clear()
rss = '<rss><channel><item><title>Manşet A</title><link>https://n/1</link><pubDate>Wed, 04 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'
ww._http_get = lambda url, timeout=12: rss
nm = ww.news_map("ekonomi", 1)
tr = next(x for x in nm if x["ülke"] == "Türkiye")
check("haber haritası: ülkeler başkentlerine yerleşir", len(nm) == len(ww.EDITIONS) and abs(tr["lat"] - 39.93) < 0.2 and tr["haberler"][0]["başlık"] == "Manşet A", tr)

print("SANAL ŞEHİR + FİZİK")
from core.skills import world as wd  # noqa: E402
ff = wd.free_fall(45)
check("serbest düşme 45 m = 3.03 s, 107 km/s", ff["süre_s"] == 3.029 and round(ff["çarpma_hızı_kmh"]) == 107, ff)
check("Ay'da 100 m = 11.1 s", wd.free_fall(100, "Ay")["süre_s"] == 11.111)
sky = wd.free_fall(3000, "Dünya", True, 80, 0.7, 1.0)
check("paraşütçü limit hızı ~43 m/s (hava direnci)", 40 < sky["limit_hız_ms"] < 46 and abs(sky["hava_dirençli_hız_ms"] - sky["limit_hız_ms"]) < 0.5, sky)
br = wd.braking_distance(100, 0.7, 1.0)
check("100 km/s durma mesafesi ≈ 84 m", br["toplam_m"] == 84.0, br)
pj = wd.projectile(20, 45)
check("eğik atış 20 m/s 45° menzil 40.8 m", pj["menzil_m"] == 40.77, pj)
check("şehir komutu: Türkçe eş anlamlılar", wd.city_command("yerçekimi", "mars") == {"ui": "city", "action": "gravity", "value": "Mars"} and wd.city_command("hava", "karlı")["value"] == "kar")
check("şehir inşa komutu", wd.city_command("inşa", "", "ev", 500)["count"] == 200)
check("şehir top bırak + teori", wd.city_command("top", "80")["fizik"]["süre_s"] == 4.039)
check("geçersiz işlem reddedilir", wd.city_command("uç").startswith("Bilinmeyen"))

print("DİJİTAL İKİZ + BİYOLOJİ")
from core.skills import twin as tw  # noqa: E402
import threading as _th  # noqa: E402
from http.server import BaseHTTPRequestHandler as _BH, ThreadingHTTPServer as _TS  # noqa: E402
pc = tw.pc_twin_data(); time.sleep(0.3); pc = tw.pc_twin_data()
check("PC ikizi: çekirdek, RAM, disk, hız verileri", len(pc["çekirdekler"]) >= 1 and 0 < pc["ram_yüzde"] < 100 and pc["diskler"] and pc["disk_okuma_mbs"] >= 0, {k: pc[k] for k in ("cpu", "ram_yüzde")})
pdb = "\n".join(["HEADER    TEST", "TITLE     DENEME PROTEINI", "HELIX    1   1 ALA A    2  ALA A    5  1                                   4",
                 "SHEET    1   A 2 GLY B   1  GLY B   3  0"] +
                ["ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00 20.00           C" % (i, i, i * 1.0, 0.0, 0.0) for i in range(1, 7)] +
                ["ATOM  %5d  CA  GLY B%4d    %8.3f%8.3f%8.3f  1.00 20.00           C" % (10 + i, i, 0.0, i * 1.0, 0.0) for i in range(1, 4)] +
                ["HETATM   20 FE   HEM A 100      10.000  10.000  10.000  1.00 20.00          FE", "ENDMDL", "ATOM     99  CA  ALA A   1       0.0     0.0     0.0  1.00 20.00           C"])
at, he, sh = tw.parse_pdb(pdb)
check("PDB ayrıştırma (ATOM/HETATM/HELIX/SHEET, ilk model)", len(at) == 10 and he == [("A", 2, 5)] and sh == [("B", 1, 3)] and at[-1]["el"] == "FE" and at[-1]["het"], (len(at), he, sh))
cif = """data_X
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.auth_seq_id
_atom_site.auth_asym_id
_atom_site.pdbx_PDB_model_num
ATOM 1 N N ALA A 1 1.0 2.0 3.0 1 A 1
ATOM 2 C CA ALA A 1 1.5 2.5 3.5 1 A 1
HETATM 3 ZN ZN ZN C . 5.0 5.0 5.0 101 A 1
ATOM 4 C CA ALA A 1 9 9 9 1 A 2
#"""
ca, _, _ = tw.parse_cif(cif)
check("mmCIF ayrıştırma (yalnızca 1. model)", len(ca) == 3 and ca[1]["name"] == "CA" and ca[2]["el"] == "ZN" and ca[2]["het"], ca)
(Path(os.environ["JARVIS_DATA"]) / "pdb").mkdir(exist_ok=True)
(Path(os.environ["JARVIS_DATA"]) / "pdb" / "9ZZZ.txt").write_text(pdb, encoding="utf-8")
tw._get = lambda *a, **k: (_ for _ in ()).throw(OSError("çevrimdışı"))
pd = tw.protein_data("9zzz")
check("protein verisi (önbellekten, çevrimdışı)", pd["info"]["kod"] == "9ZZZ" and pd["info"]["zincir"] == 2 and pd["info"]["ligandlar"] == ["HEM"] and pd["info"]["başlık"] == "DENEME PROTEINI", pd["info"])
check("bilinen ad → PDB kodu", tw.protein_search("Hemoglobin") == ["4HHB"] and tw.protein_search("1abc") == ["1ABC"])
check("hücre ve ikiz komutları", tw.cell_show("bitki") == {"ui": "bio", "kind": "cell", "cell": "plant"} and tw.digital_twin("ev")["kind"] == "home")
# sahte Home Assistant
_ha_state = {"light.salon": "off"}
class _HA(_BH):
    def log_message(self, *a): pass
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/api/states":
            self._j([{"entity_id": "light.salon", "state": _ha_state["light.salon"], "attributes": {"friendly_name": "Salon ışığı"}},
                     {"entity_id": "sensor.salon_sicaklik", "state": "22.4", "attributes": {"friendly_name": "Salon sıcaklık", "unit_of_measurement": "°C"}},
                     {"entity_id": "switch.kahve", "state": "on", "attributes": {"friendly_name": "Kahve makinesi"}}])
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/template":
            b = json.dumps([{"ad": "Salon", "cihazlar": ["light.salon", "sensor.salon_sicaklik"]}]).encode()
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(b)
        elif self.path == "/api/services/light/toggle":
            _ha_state["light.salon"] = "on" if _ha_state["light.salon"] == "off" else "off"; self._j([])
_has = _TS(("127.0.0.1", 0), _HA); _th.Thread(target=_has.serve_forever, daemon=True).start()
os.environ["HA_URL"] = f"http://127.0.0.1:{_has.server_address[1]}"; os.environ["HA_TOKEN"] = "x"
hd = tw.home_twin_data()
check("ev ikizi: odalar Home Assistant'tan (oda + odasız)", hd["bağlı"] and hd["odalar"][0]["ad"] == "Salon" and len(hd["odalar"][0]["cihazlar"]) == 2 and hd["odalar"][1]["cihazlar"][0]["id"] == "switch.kahve", hd)
tw.home_toggle("light.salon")
check("ev ikizinden ışık aç/kapat", _ha_state["light.salon"] == "on" and tw.home_toggle("sensor.salon_sicaklik") == "Bu cihaz aç/kapat desteklemiyor.")
_has.shutdown(); os.environ.pop("HA_URL"); os.environ.pop("HA_TOKEN")

print("FİNANS LABORATUVARI")
from core.skills import financelab as fl  # noqa: E402
import math as _m  # noqa: E402
import random as _r  # noqa: E402
_r.seed(3); _px = [100.0]
for _ in range(1300):
    _px.append(_px[-1] * _m.exp(0.0003 + _r.gauss(0, 0.011)))
_dates = [f"2021-{(i // 28) % 12 + 1:02d}-{i % 28 + 1:02d}" for i in range(len(_px))]
fl._history = lambda sym, rng="5y": (_dates, _px, "TRY")
bt = fl.backtest("bist100", "sma", "5y", 50, 200)
check("geri test: al-tut toplam getirisi fiyat oranına eşit", abs(bt["al_tut_sonuç"]["toplam_getiri_%"] - (_px[-1] / _px[0] - 1) * 100) < 0.01, bt["al_tut_sonuç"])
check("geri test: işlem sayısı + grafik serisi", bt["strateji_sonuç"]["işlem_sayısı"] > 0 and len(bt["seri"]["strateji"]) == len(bt["seri"]["tarih"]) and bt["ui"] == "finlab")
eq, tr, ex = fl.run_backtest([1, 2, 3, 4, 5], "hold", fee=0)
check("al-tut özsermaye = fiyat/ilk fiyat", eq == [1.0, 2.0, 3.0, 4.0, 5.0] and tr == 1)
check("maksimum düşüş", round(fl._maxdd([100, 120, 60, 90, 130]), 3) == -0.5)
check("RSI sürekli yükselişte 100", fl._rsi(list(range(1, 20)))[-1] == 100)
check("kredi taksiti (1M, %36, 36 ay) = 45.803,79", fl.loan_calc(1000000, 36, 36)["aylık_taksit"] == 45803.79)
check("faizsiz kredi", fl.loan_calc(120000, 0, 12)["aylık_taksit"] == 10000 and fl.loan_calc(120000, 0, 12)["toplam_faiz"] == 0)
check("bileşik faiz %10 aylık bileşik 1 yıl", fl.compound_growth(1000, 10, 1)["son_değer"] == 1104.71)
mc = fl.monte_carlo(100000, 0, 10, 7, 0.0001, 0, 0, 200, 1)
check("Monte Carlo sıfır oynaklıkta = %7 bileşik", abs(mc["medyan_son"] - 100000 * 1.07 ** 10) < 50, mc["medyan_son"])
mc = fl.monte_carlo(100000, 5000, 20, 10, 18, 0, 3000000, 1500, 7)
check("Monte Carlo bantları sıralı + hedef olasılığı", mc["kötü_senaryo_p10"] < mc["medyan_son"] < mc["iyi_senaryo_p90"] and 0 < mc["hedefe_ulaşma_olasılığı_%"] < 100 and len(mc["bantlar"]["p50"]) == 20, mc["hedefe_ulaşma_olasılığı_%"])
fl._quote = lambda sym, rng="5d": {"sembol": sym, "fiyat": {"USDTRY=X": 40.0, "EURTRY=X": 45.0, "AAPL": 200.0, "THYAO.IS": 300.0}.get(sym, 1.0), "para": "USD" if sym == "AAPL" else "TRY", "değişim_%": 1.0}
fl.portfolio_add("AAPL", 10, 150); fl.portfolio_add("THYAO.IS", 100, 250)
pf = fl.portfolio_show()
check("portföy TL değeri (döviz çevrimli) + K/Z", pf["toplam_TL"] == 10 * 200 * 40 + 100 * 300 and pf["kâr_zarar_TL"] == 10 * 50 * 40 + 100 * 50, pf)
check("portföy payları %100", abs(sum(a["pay_%"] for a in pf["varlıklar"]) - 100) < 0.2)

print("MÜZİK")
from core.skills import music as mu  # noqa: E402


def _parse_midi(b):
    """Bağımsız SMF çözücü: başlık, iz sayısı, nota sayısı, toplam süre (sn)."""
    import struct as _st
    assert b[:4] == b"MThd"
    _, fmt, ntr, tpq = _st.unpack(">IHHH", b[4:14])
    i, tracks, notes, tempo, maxt = 14, 0, 0, 500000, 0
    while i < len(b):
        assert b[i:i + 4] == b"MTrk", b[i:i + 4]
        ln = _st.unpack(">I", b[i + 4:i + 8])[0]
        j, end, t = i + 8, i + 8 + ln, 0
        while j < end:
            v = 0
            while True:
                c = b[j]; j += 1; v = (v << 7) | (c & 0x7F)
                if not c & 0x80:
                    break
            t += v
            st = b[j]
            if st == 0xFF:
                typ, L = b[j + 1], b[j + 2]
                if typ == 0x51:
                    tempo = int.from_bytes(b[j + 3:j + 6], "big")
                j += 3 + L
            elif st >> 4 in (0x8, 0x9):
                if st >> 4 == 0x9 and b[j + 2] > 0:
                    notes += 1
                j += 3
            elif st >> 4 == 0xC:
                j += 2
            else:
                raise AssertionError(hex(st))
        maxt = max(maxt, t)
        tracks += 1
        i = end
    return {"format": fmt, "tracks": tracks, "declared": ntr, "notes": notes, "seconds": maxt / tpq * tempo / 1e6}


sg = mu.compose("caz", "", 120, 8, "C", 3)
md = _parse_midi(mu.to_midi(sg))
check("MIDI geçerli: format 1, iz sayısı, tüm notalar", md["format"] == 1 and md["tracks"] == md["declared"] == 5 and md["notes"] == sum(len(t["notes"]) for t in sg["tracks"]) + len(sg["drums"]), md)
check("MIDI süresi = ölçü × 4 × 60 / BPM (8 ölçü @120 = 16 sn)", 15.5 < md["seconds"] <= 16.3, md["seconds"])
check("ton ve dizi: C majör, akorlar doğru nitelikte", sg["key"] == "C" and all(c in ("C", "Dm", "Em", "F", "G", "Am", "B°") for c in sg["progression"]), sg["progression"])
_pg = mu.compose("piyano", "", 0, 16, "C", 9)
check("tüm notalar dizide (melodi/akor/bas; caz dışı)", all(n[2] % 12 in (0, 2, 4, 5, 7, 9, 11) for t in _pg["tracks"] for n in t["notes"]))
check("caz swing: 8'lik arka vuruşlar 2/3'te", any(abs((d[0] % 1) - 0.66) < 0.01 for d in sg["drums"]))
check("hüzünlü → minör, ton ayrıştırma", mu.compose("piyano", "hüzünlü", 0, 8, "", 1)["scale"] == "minor" and mu._key("F# minör") == (6, "minor") and mu._key("Sol") == (7, None))
dr = mu.drum_beat("trap", 140, 4)
check("davul ritmi: yalnızca davul, MIDI kaydedildi", dr["song"]["tracks"] == [] and len(dr["song"]["drums"]) > 40 and Path(dr["midi"]).exists() and _parse_midi(Path(dr["midi"]).read_bytes())["tracks"] == 2)
check("tüm türler üretilebilir", all(mu.compose(s_, "", 0, 8, "", 2)["bars"] == 8 for s_ in mu.STYLES))

print("TARAYICI OTOMASYONU · OBS · FATURA")
try:
    import playwright  # noqa: F401
    _has_pw = True
except ImportError:
    _has_pw = False
if _has_pw:
    import http.server as _hs
    import functools as _ft
    _site = Path(tempfile.mkdtemp())
    (_site / "index.html").write_text('<!doctype html><html><head><meta charset="utf-8"><title>Uçuş</title></head><body><form action="s.html"><label for="a">Nereden</label><input id="a" name="a">'
                                      '<select name="c" aria-label="Sınıf"><option>Ekonomi</option><option>Business</option></select><input type="password" aria-label="Şifre" name="p">'
                                      '<button type="submit">Ara</button></form><button>Hesabı sil</button></body></html>', encoding="utf-8")
    (_site / "s.html").write_text('<!doctype html><meta charset="utf-8"><title>Sonuç</title><p id=r></p><script>r.innerText=location.search</script>', encoding="utf-8")
    class _QH(_hs.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    _hsrv = _hs.ThreadingHTTPServer(("127.0.0.1", 0), _ft.partial(_QH, directory=str(_site)))
    _th.Thread(target=_hsrv.serve_forever, daemon=True).start()
    os.environ["JARVIS_BROWSER_HEADLESS"] = "1"; os.environ.setdefault("JARVIS_BROWSER_CHANNEL", "chromium")
    from core.skills import browser as bw  # noqa: E402
    try:
        r = bw.browser_open(f"http://127.0.0.1:{_hsrv.server_address[1]}/index.html")
        check("tarayıcı: sayfa + numaralı öğeler", r["başlık"] == "Uçuş" and any("ŞİFRE" in e for e in r["öğeler"]) and any("Hesabı sil" in e for e in r["öğeler"]), r["öğeler"])
        bw.browser_fill("Nereden", "İzmir"); bw.browser_fill("Sınıf", "Business")
        check("şifre alanına yazmayı reddeder", "yazmam" in bw.browser_fill("Şifre", "1234"))
        sil_no = next(e for e in r["öğeler"] if "Hesabı sil" in e).split("]")[0].strip("[")
        check("riskli düğme her zaman onaylı (yazı ve numara ile)", tools.is_critical("browser_click", {"target": "Hesabı sil"}) and tools.is_critical("browser_click", {"target": sil_no}))
        rr = bw.browser_click("Ara")
        check("form gönderildi, değerler doğru", rr["başlık"] == "Sonuç" and "a=%C4%B0zmir" in rr["metin"] and "c=Business" in rr["metin"], rr["metin"])
        check("sekmeler", len(bw.browser_tabs("list")) == 1)
    finally:
        bw.browser_close(); _hsrv.shutdown()
else:
    print("  (playwright yok: tarayıcı testleri atlandı)")

# sahte OBS WebSocket v5 sunucusu (kimlik doğrulamalı)
import base64 as _b64  # noqa: E402
import hashlib as _hl  # noqa: E402
import socket as _sk  # noqa: E402
import struct as _st2  # noqa: E402
_obs_state = {"rec": False, "scene": "Oyun"}
def _obs_srv(lsock, pw="gizli"):
    salt, chal = "tuz", "meydan"
    want = _b64.b64encode(_hl.sha256((_b64.b64encode(_hl.sha256((pw + salt).encode()).digest()).decode() + chal).encode()).digest()).decode()
    while True:
        c, _ = lsock.accept()
        req = b""
        while b"\r\n\r\n" not in req:
            req += c.recv(1024)
        key = [l.split(b": ")[1] for l in req.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
        acc = _b64.b64encode(_hl.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + acc + b"\r\n\r\n")
        def send(o):
            d = json.dumps(o).encode(); c.sendall(bytes([0x81, len(d)]) + d if len(d) < 126 else bytes([0x81, 126]) + _st2.pack(">H", len(d)) + d)
        def recv():
            h = c.recv(2); n = h[1] & 0x7F
            if n == 126: n = _st2.unpack(">H", c.recv(2))[0]
            m = c.recv(4); d = b""
            while len(d) < n: d += c.recv(n - len(d))
            return json.loads(bytes(b ^ m[i % 4] for i, b in enumerate(d)))
        try:
            send({"op": 0, "d": {"rpcVersion": 1, "authentication": {"salt": salt, "challenge": chal}}})
            ident = recv()
            if ident["d"].get("authentication") != want:
                c.close(); continue
            send({"op": 2, "d": {"negotiatedRpcVersion": 1}})
            while True:
                q = recv()["d"]; t = q["requestType"]; data = {}
                if t == "StartRecord": _obs_state["rec"] = True
                elif t == "StopRecord": _obs_state["rec"] = False; data = {"outputPath": "C:/Videos/kayit.mkv"}
                elif t == "GetRecordStatus": data = {"outputActive": _obs_state["rec"], "outputTimecode": "00:00:05"}
                elif t == "GetStreamStatus": data = {"outputActive": False}
                elif t == "GetCurrentProgramScene": data = {"currentProgramSceneName": _obs_state["scene"]}
                elif t == "SetCurrentProgramScene": _obs_state["scene"] = q["requestData"]["sceneName"]
                elif t == "GetSceneList": data = {"scenes": [{"sceneName": "Sohbet"}, {"sceneName": "Oyun"}]}
                send({"op": 7, "d": {"requestType": t, "requestId": q["requestId"], "requestStatus": {"result": True, "code": 100}, "responseData": data}})
        except Exception:
            c.close()
_ls = _sk.socket(); _ls.bind(("127.0.0.1", 0)); _ls.listen(5)
_th.Thread(target=_obs_srv, args=(_ls,), daemon=True).start()
os.environ["OBS_PORT"] = str(_ls.getsockname()[1])
from core.skills import games as gm  # noqa: E402
os.environ["OBS_PASSWORD"] = "yanlis"
def _try(f):
    try:
        return f()
    except Exception as e:
        return str(e)
check("OBS: yanlış parola reddedilir", "başarısız" in _try(lambda: gm.obs_control("status")) or "kapandı" in _try(lambda: gm.obs_control("status")))
os.environ["OBS_PASSWORD"] = "gizli"
gm.obs_control("record_start")
st = gm.obs_control("status")
check("OBS: kimlik doğrulama + kayıt başladı", st["kayıt"] == "açık" and st["sahne"] == "Oyun", st)
check("OBS: sahne listesi ve değiştirme", gm.obs_control("scenes") == ["Oyun", "Sohbet"] and gm.obs_control("scene", "Sohbet") == "Sahne değişti: Sohbet" and _obs_state["scene"] == "Sohbet")
check("OBS: kaydı durdur → dosya yolu", gm.obs_control("record_stop")["dosya"] == "C:/Videos/kayit.mkv" and not _obs_state["rec"])
check("OBS: yayın başlatma onaylı", tools.is_critical("obs_control", {"action": "stream_start"}) and not tools.is_critical("obs_control", {"action": "record_start"}))
from core.skills import office as of  # noqa: E402
inv = of.invoice_create("Ali Veli", "Danışmanlık;10;1.250,00 | Yazılım;1;5000", 20, "TL", "Benim Şirketim")
from pypdf import PdfReader as _PR  # noqa: E402
_t = _PR(inv["fatura"]).pages[0].extract_text()
check("fatura: hesap (ara toplam 17.500, KDV 3.500, toplam 21.000) + PDF metni", inv["ara_toplam"] == 17500 and inv["kdv"] == 3500 and inv["genel_toplam"] == 21000 and "21.000,00 TL" in _t and "Ali Veli" in _t, inv)
check("fatura: hatalı kalem anlaşılır hata", "okunamadı" in str(of.invoice_create("x", "Kalem;iki;10")))

print("SES LABORATUVARI")
import asyncio as _aio  # noqa: E402
from core import voice as _vc, config as _cf  # noqa: E402
_calls = []
class _FC:
    def __init__(self, text, voice, rate="+0%", pitch="+0Hz"): _calls.append((voice, rate, pitch))
    async def stream(self):
        yield {"type": "audio", "data": b"ID3"}
class _FE:
    Communicate = _FC
    @staticmethod
    async def list_voices():
        return [{"ShortName": "tr-TR-AhmetNeural", "Locale": "tr-TR", "Gender": "Male"}, {"ShortName": "en-GB-RyanNeural", "Locale": "en-GB", "Gender": "Male"},
                {"ShortName": "en-US-AndrewMultilingualNeural", "Locale": "en-US", "Gender": "Male"}, {"ShortName": "fr-FR-RemyMultilingualNeural", "Locale": "fr-FR", "Gender": "Male"},
                {"ShortName": "ja-JP-KeitaNeural", "Locale": "ja-JP", "Gender": "Male"}]
_vc.edge_tts = _FE
_vc._voice_cache.update({"t": 0, "v": []})
vl = _aio.run(_vc.list_voices())
check("ses listesi: Türkçe + İngilizce + çok dilli (Japonca hariç)", [v["name"] for v in vl][0] == "tr-TR-AhmetNeural" and len(vl) == 4 and all(v["tr"] for v in vl if v["multilingual"]), [v["name"] for v in vl])
_cf.save_settings({"voice_pick": {"ultron": {"tr": "en-US-AndrewMultilingualNeural"}}, "voice": {"ultron": {"rate": 5, "pitch": -10}}})
_aio.run(_vc.synthesize("Merhaba", "ultron", "tr"))
check("kaydedilen ses + hız/ton kullanılır", _calls[-1][0] == "en-US-AndrewMultilingualNeural" and _calls[-1][1] == "-7%" and _calls[-1][2] == "-34Hz", _calls[-1])
_aio.run(_vc.synthesize("Merhaba", "ultron", "tr", "", "tr-TR-AhmetNeural", 0, 0))
check("önizleme geçici ayarları kaydı değiştirmez", _calls[-1] == ("tr-TR-AhmetNeural", "-12%", "-24Hz") and _cf.load_settings()["voice_pick"]["ultron"]["tr"] == "en-US-AndrewMultilingualNeural", _calls[-1])
_aio.run(_vc.synthesize("Hello", "jarvis", "en"))
check("seçim yoksa film varsayılanı (İngiliz Ryan)", _calls[-1][0] == "en-GB-RyanNeural")

print("GÖRSEL STÜDYO")
import io as _io  # noqa: E402
import shutil as _sh  # noqa: E402
import subprocess as _sp0  # noqa: E402
from PIL import Image as _Im  # noqa: E402
from core.skills import studio as st  # noqa: E402
st.OUT, st.VOUT = HOME / "Pictures" / "JARVIS", HOME / "Videos" / "JARVIS"
_b = _io.BytesIO(); _Im.new("RGB", (64, 64), "red").save(_b, "PNG")
st._pollinations = lambda *a: _b.getvalue()
g = st.image_generate("kırmızı kare", "minimal", 512, 512, 7, 2)
check("resim üretme: 2 varyant kaydedildi + ekranda gösterilir", g["ui"] == "image" and len(g["files"]) == 2 and all(Path(f).exists() for f in g["files"]) and "_7.png" in g["files"][0], g)
st._pollinations = lambda *a: (_ for _ in ()).throw(OSError("ağ yok"))
check("servis yoksa dürüst hata", "üretilemedi" in st.image_generate("x"))
_Im.new("RGB", (800, 500), "#3366cc").save(HOME / "p.jpg")
e = st.photo_edit(str(HOME / "p.jpg"), "crop:10,20,300,200,sepia,text:Merhaba,watermark:© Ben")
check("fotoğraf düzenleme zinciri (kırp/sepya/yazı/filigran)", e["boyut"] == "300x200" and Path(e["path"]).exists(), e)
r = st.photo_edit(str(HOME / "p.jpg"), "remove_bg:#3366cc")
check("düz arka planı saydam yap", _Im.open(r["path"]).getpixel((5, 5))[3] == 0)
check("döndür + çerçeve + format", st.photo_edit(str(HOME / "p.jpg"), "rotate:90,border:20:#ff0000,format:png")["boyut"] == "540x840")
check("bilinmeyen işlem reddedilir", st.photo_edit(str(HOME / "p.jpg"), "uçur") == "Bilinmeyen işlem: uçur")
lg = st.logo_make("Kahraman Tech", "geleceği kodla")
import xml.dom.minidom as _md  # noqa: E402
check("logo: 4 geçerli SVG + PNG önizleme", len(lg["files"]) == 4 and all(_md.parse(f) for f in lg["files"]) and lg["path"].endswith(".png"))
if _sh.which("ffmpeg") and _sh.which("ffprobe"):
    v = HOME / "t.mp4"
    _sp0.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=red:s=320x180:d=2", "-f", "lavfi", "-i", "testsrc=s=320x180:d=2", "-f", "lavfi", "-i", "sine=duration=4",
              "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-shortest", str(v)],
             capture_output=True, check=True)
    inf = st.video_info(str(v))
    check("video bilgisi", inf["süre_sn"] == 4.0 and inf["çözünürlük"] == "320x180" and inf["ses"] != "yok", inf)
    check("sahne değişimi bulundu (2. sn)", any(abs(t - 2) < 0.2 for t in st.video_scenes(str(v), 0.3)["sahne_başlangıçları_sn"]))
    check("kes 1–3 sn → 2 sn", abs(st.video_info(st.video_edit(str(v), "cut", "1", "3")["çıktı"])["süre_sn"] - 2) < 0.15)
    check("2× hızlandır", abs(st.video_info(st.video_edit(str(v), "speed", value="2")["çıktı"])["süre_sn"] - 2) < 0.2)
    check("sessize al + müzik ekle", st.video_info(st.video_edit(str(v), "mute")["çıktı"])["ses"] == "yok")
    check("GIF + küçük resim", Path(st.video_edit(str(v), "to_gif", "0", "1")["çıktı"]).stat().st_size > 1000 and Path(st.video_edit(str(v), "thumbnail", "1")["çıktı"]).exists())
    check("birleştir 4+2 sn", abs(st.video_info(st.video_merge(f"{v};{st.VOUT / 't_cut.mp4'}")["path"])["süre_sn"] - 6) < 0.2)
    m = st.video_montage(f"{HOME / 'p.jpg'};{lg['path']}", seconds=2, title="Tatil: 2026")
    check("resimlerden montaj 2×2 sn, 720p", abs(st.video_info(m["path"])["süre_sn"] - 4) < 0.2 and st.video_info(m["path"])["çözünürlük"] == "1280x720")
else:
    print("  (ffmpeg yok: video testleri atlandı)")
check("galeri", len(st.studio_gallery()["files"]) >= 3)

print("YAPAY ZEKÂ EKİBİ (senaryolu sahte model)")
import socket as _s2  # noqa: E402
import subprocess as _sp  # noqa: E402
_so2 = _s2.socket(); _so2.bind(("127.0.0.1", 0)); _fport = _so2.getsockname()[1]; _so2.close()
_fake = _sp.Popen([sys.executable, str(ROOT / "tests" / "fake_llm.py"), str(_fport)])
time.sleep(0.8)
os.environ["CUSTOM_BASE_URL"] = f"http://127.0.0.1:{_fport}"
try:
    from core.skills import team  # noqa: E402
    r = team.team_task("Elektrikli araç pazarı raporu")
    res = {x["id"]: x for x in json.loads(memory._q("SELECT results FROM team_runs WHERE id=?", (r["run"],), one=True)["results"])}
    check("plan: 3 uzman görevi", len(res) == 3 and res[1]["role"] == "araştırmacı" and res[3]["role"] == "yazar")
    check("görev devri: yazar 1 ve 2'nin sonucunu aldı", "girdi:1,2" in res[3]["sonuç"], res[3]["sonuç"])
    check("denetçi düzeltme istedi, ajan yeniden yaptı", r["yeniden_yapılan"] == [2] and "düzeltildi" in res[2]["sonuç"])
    check("rol hafızası ve performans kaydı", team.team_memory("analist") != "Ekip hafızası boş." and team.team_performance()[0]["görev"] >= 1)
    p = team.team_task("onaylı", approve_plan=True)
    check("onaylı plan önce gösterilir, sonra çalışır", "plan_no" in p and team.team_run(p["plan_no"])["run"] == p["plan_no"])
    check("ajan içinden yeni ekip kurulamaz", (setattr(team._tls, "inside", True), team.team_task("x"))[1] == "Ekip üyeleri yeni ekip kuramaz.")
    team._tls.inside = False

    print("KOMUTA MERKEZİ / MODLAR / MAKROLAR")
    from core import brain as _br, config as _cfg  # noqa: E402
    from core.skills import command as cmd  # noqa: E402
    check("mod değiştir (Türkçe karaktersiz de)", cmd.set_mode("muhendislik")["mode"] == "mühendislik" and cmd.current_mode() == "mühendislik")
    tip, mg = cmd.mode_hint()
    check("mod ipucu + araç grupları", "MÜHENDİSLİK" in tip and "holo" in mg)
    check("bilinmeyen mod listelenir", cmd.set_mode("uzay").startswith("Modlar:"))
    cmd.set_mode("normal")
    cmd.macro_create("Sabah Rutini", "mod:sessiz; söyle:Günaydın; saat kaç", "günaydın jarvis")
    check("makro tetik cümlesi eşleşir", cmd.match_trigger("Günaydın Jarvis!") == "sabah rutini" and cmd.match_trigger("Jarvis, sabah rutini") == "sabah rutini" and cmd.match_trigger("merhaba") is None)
    evs = list(_br.chat("günaydın jarvis", "jarvis"))
    mr = json.loads(next(e for e in evs if e["type"] == "tool" and e["status"] == "done")["result"])
    check("söylenince makro çalışır (3 adım, model adımı dahil)", evs[-1]["provider"] == "makro" and len(mr["adımlar"]) == 3 and cmd.current_mode() == "sessiz", mr)
    check("makro modu değiştirdi ve bildirim düştü", any(n["kind"] == "mode" and n["text"] == "sessiz" for n in memory.notifications_since(0)))
    check("iç içe makro sınırı", "iç içe" in str(cmd.macro_run("sabah rutini", "", 5)))
    cmd.set_mode("normal")
    check("modül kapat", cmd.module_toggle("studio", False)["durum"] == "kapalı" and "studio" in cmd.disabled_groups())
    check("çekirdek kapatılamaz", cmd.module_toggle("core", False) == "Çekirdek modül kapatılamaz.")
    cmd.module_toggle("studio", True)
    check("modül tekrar açık", "studio" not in cmd.disabled_groups())
    snap = cmd.snapshot()
    check("komuta merkezi verisi tam", all(k in snap for k in ("sistem", "güvenlik", "ekip", "görevler", "bağlantılar", "modüller", "makrolar", "işlemler", "bildirimler", "modlar")))
    rd = cmd.readiness()
    check("kurulum durumu: model bağlı, zorunlular tamam", rd["hazır"] and any(x["bileşen"] == "Yapay zekâ modeli" and x["durum"] for x in rd["bileşenler"]) and "kurulum" in snap, rd["eksik_zorunlu"])
    check("makro silme", cmd.macro_delete("sabah rutini") == "Silindi." and cmd.macro_delete("yok") == "Böyle bir makro yok.")

    print("BİLGİ MERKEZİ")
    from core.skills import knowledge as kn  # noqa: E402
    import docx as _docx  # noqa: E402
    import zipfile as _zf  # noqa: E402
    lib = HOME / "kutuphane"; lib.mkdir()
    (lib / "uzay.txt").write_text("Mars kırmızı gezegendir. Mars'ın iki uydusu vardır: Phobos ve Deimos.\n\nJüpiter en büyük gezegendir.", encoding="utf-8")
    dd = _docx.Document(); dd.add_paragraph("Fotosentez bitkilerin kloroplastlarında gerçekleşir. Işık enerjisi glikoza dönüşür."); dd.save(lib / "biyoloji.docx")
    with _zf.ZipFile(lib / "tarih.epub", "w") as z:
        z.writestr("OEBPS/ch1.xhtml", "<html><body><h1>Cumhuriyet</h1><p>Türkiye Cumhuriyeti 1923 yılında ilan edildi. Başkent Ankara oldu.</p></body></html>")
    from reportlab.pdfgen import canvas as _cv  # noqa: E402
    c = _cv.Canvas(str(lib / "kuantum.pdf")); c.drawString(72, 750, "Quantum entanglement links particles across distance."); c.showPage(); c.drawString(72, 750, "Superposition means many states at once."); c.save()
    r = kn.library_add(str(lib))
    check("klasörden 4 tür belge eklendi (txt/docx/epub/pdf)", r["eklenen"] == 4 and r["atlanan"] == 0, r)
    ls = kn.library_list()
    check("kütüphane listesi + pdf 2 sayfa", len(ls) == 4 and next(d for d in ls if d["tür"] == "pdf")["sayfa"] == 2, ls)
    h = kn.library_search("Mars'ın uyduları")
    check("BM25 arama doğru belge", h[0]["belge"] == "uzay", h)
    h = kn.library_search("superposition")
    check("PDF 2. sayfa bulundu", h[0]["belge"] == "kuantum" and h[0]["sayfa"] == 2, h)
    check("Türkçe ek/gövde eşleşmesi", kn.library_search("kloroplastlar")[0]["belge"] == "biyoloji")
    a = kn.library_ask("Cumhuriyet ne zaman ilan edildi?")
    check("kaynaklı cevap + kaynak listesi", a["cevap"].startswith("Kaynağa göre") and a["kaynaklar"][0]["belge"] == "tarih", a)
    check("kütüphane yeniden ekleme yinelenmez", (kn.library_add(str(lib / "uzay.txt")), len(kn.library_list()))[1] == 4)
    g = kn.knowledge_graph(doc="tarih")
    check("AI bilgi grafiği (geçersiz kenar elendi)", g["ui"] == "graph" and len(g["edges"]) == 2 and g["yöntem"].startswith("yapay"), g)
    g2 = kn.knowledge_graph(doc="uzay", use_ai=False)
    check("yerel grafik (modelsiz)", g2["ui"] == "graph" and any(n["id"].startswith("Mars") for n in g2["nodes"]), g2["nodes"][:5])
    q = kn.quiz_make("fotosentez", 3)
    check("quiz: geçersiz soru elendi, kartlar kaydedildi", q["ui"] == "quiz" and len(q["questions"]) == 2 and all("id" in x for x in q["questions"]), q)
    c1 = kn.card_answer(q["questions"][0]["id"], 0); c2 = kn.card_answer(q["questions"][1]["id"], 3)
    check("Leitner: doğru → kutu 2 (1 gün), yanlış → kutu 1", c1["doğru"] and c1["kutu"] == 2 and not c2["doğru"] and c2["kutu"] == 1)
    check("tekrar zamanı gelen kart yok (yanlış 10 dk sonra)", isinstance(kn.study_review(), str))
    st = kn.study_stats()
    check("öğrenme istatistiği", st[0]["kart"] == 2 and st[0]["başarı_%"] == 50, st)
    lp = kn.learning_plan("Python öğren", 2, 5)
    check("öğrenme planı + yapılacaklara eklendi", lp["hafta"] == 2 and lp["yapılacaklara_eklenen"] == 3, lp)
    import types as _ty  # noqa: E402
    _fake_tts = _ty.ModuleType("edge_tts")
    class _Com:  # noqa: E306
        def __init__(self, text, voice, rate="+0%"): self.t = text
        async def save(self, f): Path(f).write_bytes(b"ID3" + self.t.encode()[:50])
    _fake_tts.Communicate = _Com
    sys.modules["edge_tts"] = _fake_tts
    (lib / "uzun.txt").write_text("\n".join(f"Paragraf {i}: " + "Uzun bir kitap cümlesi. " * 30 for i in range(40)), encoding="utf-8")
    kn.library_add(str(lib / "uzun.txt"))
    ab = kn.audiobook("uzun")
    for _ in range(50):
        if kn._jobs[ab["iş"]]["durum"] != "çalışıyor":
            break
        time.sleep(0.1)
    mp3 = sorted(Path(ab["klasör"]).glob("*.mp3"))
    check("sesli kitap: bölümler mp3 olarak üretildi", kn._jobs[ab["iş"]]["durum"] == "bitti" and len(mp3) == ab["bölüm"] >= 3, (ab, kn._jobs))
    full = kn._doc_text(kn._doc("uzun")["id"])
    check("sesli kitap metninde örtüşme tekrarı yok", all(full.count(f"Paragraf {i}:") == 1 for i in range(40)) and full.count("Uzun bir kitap cümlesi.") == 1200,
          [i for i in range(40) if full.count(f"Paragraf {i}:") != 1][:5])
    check("belge kaldır", kn.library_remove("kuantum").startswith("Kaldırıldı") and len(kn.library_list()) == 4)

    print("SABAH BRİFİNGİ · OTOMATİK BAŞLAT")
    from core.skills import automation as au  # noqa: E402
    import time as _t  # noqa: E402
    sent = []
    _cfg.save_settings({"briefing": {"on": True, "time": "00:00"}, "briefing_last": ""})
    _real_lt = _t.localtime
    au.time.localtime = lambda *a: _real_lt(_t.mktime((2026, 11, 5, 1, 30, 0, 0, 0, -1)))
    au.briefing_tick(lambda txt, kind: sent.append((kind, txt)))
    check("brifing saati gelince gönderilir (bir kez)", len(sent) == 1 and sent[0][0] == "briefing" and sent[0][1], sent)
    au.briefing_tick(lambda txt, kind: sent.append((kind, txt)))
    check("aynı gün ikinci kez gönderilmez", len(sent) == 1)
    _cfg.save_settings({"briefing": {"on": True, "time": "09:00"}, "briefing_last": ""})
    au.briefing_tick(lambda txt, kind: sent.append((kind, txt)))
    check("saati gelmeden gönderilmez", len(sent) == 1)
    _cfg.save_settings({"briefing": {"on": False}})
    au.time.localtime = _real_lt
    import core.skills.command as _cm  # noqa: E402
    _cm_sys = __import__("sys")
    _old_plat, _old_app = _cm_sys.platform, os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(HOME / "AppData" / "Roaming"); _cm_sys.platform = "win32"
    try:
        r = _cm.autostart(True)
        f = _cm._startup_file()
        check("Windows ile başlat: Başlangıç klasörüne kısayol", r["durum"] == "açık" and f.exists() and "start.bat" in f.read_text(encoding="utf-8") and _cm.autostart_status())
        _cm.autostart(False)
        check("otomatik başlatma kapatılır", not f.exists() and not _cm.autostart_status())
    finally:
        _cm_sys.platform = _old_plat
        if _old_app is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = _old_app

    print("ÇEVİRİ MERKEZİ")
    from core.skills import media as _media, translate as trm  # noqa: E402
    check("dil kodları (ad/kod/Whisper)", trm.code("Almanca") == "de" and trm.code("EN") == "en" and trm.code("en-US") == "en" and trm.WHISPER2CODE["turkish"] == "tr")
    check("metin çevirisi", trm.translate_text("Merhaba dünya", "İngilizce") == "[İngilizce] Merhaba dünya", trm.translate_text("Merhaba dünya", "en"))
    mm = trm.translate_multi("Selam", "en,de,ar")
    check("aynı anda çok dile", list(mm) == ["İngilizce", "Almanca", "Arapça"] and mm["Almanca"] == "[Almanca] Selam", mm)
    _media.transcribe_verbose = lambda d, f, m, l="": ("Good morning", "english", [{"start": 0.0, "end": 1.5, "text": " Good morning"}, {"start": 61.25, "end": 3725.04, "text": " See you"}])
    a = trm.detect_and_translate_audio(b"x", "a.webm", "audio/webm", "tr", "en")
    check("ses: dil tanındı → Türkçeye", a["dil"] == "en" and a["hedef"] == "tr" and a["çeviri"] == "[Türkçe] Good morning", a)
    _media.transcribe_verbose = lambda d, f, m, l="": ("Merhaba", "turkish", [])
    a = trm.detect_and_translate_audio(b"x", "a.webm", "audio/webm", "tr", "de")
    check("iki yönlü: Türkçe konuşulunca öbür dile", a["dil"] == "tr" and a["hedef"] == "de" and a["çeviri"] == "[Almanca] Merhaba", a)
    _media.transcribe_verbose = lambda d, f, m, l="": ("x", "english", [{"start": 0.0, "end": 1.5, "text": " Good morning"}, {"start": 61.25, "end": 3725.04, "text": " See you"}])
    vid = HOME / "film.mp4"; vid.write_bytes(b"\0" * 100)
    st = trm.make_subtitles(str(vid), "tr")
    srt = Path(st["altyazı"]).read_text(encoding="utf-8")
    check("SRT zamanlama + çeviri", "00:01:01,250 --> 01:02:05,040" in srt and "[Türkçe] Good morning" in srt and srt.startswith("1\n00:00:00,000 --> 00:00:01,500"), srt)
    check("tercüman paneli komutu", trm.translator_mode("tr", "Arapça") == {"ui": "translator", "a": "tr", "b": "ar", "a_adı": "Türkçe", "b_adı": "Arapça"})
    check("çeviri grubu seçimi", "translate" in tools.pick_groups("bunu almancaya çevir"))
    from core import voice as _voice  # noqa: E402
    check("20+ dil için sinir ağı sesi", len(_voice.LANG_VOICES) >= 20 and all(v[0].endswith("Neural") for v in _voice.LANG_VOICES.values()))
finally:
    _fake.terminate()

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
