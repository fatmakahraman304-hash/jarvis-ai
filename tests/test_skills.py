"""Yetenek modülleri testi (internet ve gerçek hesap gerektirmez; Google/HA sahte API ile denenir).

Çalıştır: python tests/test_skills.py
"""
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HA_URL", "")
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis_test_")

from core import tools  # noqa: E402
from core.skills import LOAD_ERRORS, automation, finance, google, office, smarthome, windows  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


print("YÜKLEME")
check("tüm modüller yüklendi", not LOAD_ERRORS, LOAD_ERRORS)
check("100+ araç", len(tools.TOOLS) > 100, len(tools.TOOLS))
for n, (fn, sch, crit) in tools.TOOLS.items():
    if not (callable(fn) and "description" in sch and sch["parameters"]["type"] == "object"):
        check(f"şema {n}", False)

print("GMAIL / TAKVİM (sahte Google API)")
calls = []
b64 = lambda s: base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
MSG = {"id": "m1", "threadId": "t1", "labelIds": ["INBOX", "UNREAD", "IMPORTANT"], "snippet": "Yarınki toplantı",
       "payload": {"mimeType": "multipart/alternative", "headers": [
           {"name": "From", "value": "Ali Veli <ali@example.com>"}, {"name": "Subject", "value": "Toplantı"},
           {"name": "Date", "value": "Wed, 4 Nov 2026 10:00"}, {"name": "Message-ID", "value": "<abc@mail>"}],
           "parts": [{"mimeType": "text/plain", "body": {"data": b64("Merhaba, yarın 14:00 uygun mu?")}},
                     {"mimeType": "application/pdf", "filename": "ajanda.pdf", "body": {"size": 20480, "attachmentId": "a1"}}]}}


def fake_api(method, url, params=None, body=None):
    calls.append((method, url, params, body))
    if url.endswith("/messages") and method == "GET":
        return {"messages": [{"id": "m1"}]}
    if "/messages/m1" in url and method == "GET":
        return MSG
    if url.endswith("/messages/send"):
        return {"id": "sent1"}
    if url.endswith("/drafts"):
        return {"id": "d1"}
    if "/labels" in url and method == "GET" and url.endswith("/labels"):
        return {"labels": [{"name": "INBOX", "id": "INBOX"}]}
    if url.endswith("/labels") and method == "POST":
        return {"id": "Label_9"}
    if "/events" in url and method == "GET":
        return {"items": [{"id": "e1", "summary": "Dişçi", "start": {"dateTime": "2026-11-05T14:00:00+03:00"},
                           "end": {"dateTime": "2026-11-05T15:00:00+03:00"}}]}
    if "/events" in url and method == "POST":
        return {"id": "e2", **body}
    if url.endswith("/freeBusy"):
        return {"calendars": {"primary": {"busy": [{"start": "2026-11-05T11:00:00Z", "end": "2026-11-05T12:00:00Z"}]}}}
    return {}


google.api = fake_api
r = google.gmail_search("is:unread")
check("gmail_search özet", r[0]["konu"] == "Toplantı" and r[0]["okunmamış"] and r[0]["önemli"])
r = google.gmail_read("m1")
check("gmail_read gövde + ek", "14:00" in r["içerik"] and r["ekler"] and "ajanda.pdf" in r["ekler"][0])
check("okundu işaretlendi", any(c[1].endswith("/m1/modify") for c in calls))
google.gmail_reply("m1", "Uygun, görüşürüz.")
sent = [c for c in calls if c[1].endswith("/messages/send")][-1][3]
import email  # noqa: E402
from email import policy  # noqa: E402
em = email.message_from_bytes(base64.urlsafe_b64decode(sent["raw"]), policy=policy.default)
check("yanıt aynı konuda", sent.get("threadId") == "t1" and em["In-Reply-To"] == "<abc@mail>" and em["Subject"] == "Re: Toplantı"
      and "ali@example.com" in em["To"] and "görüşürüz" in em.get_content())
google.gmail_send("x@example.com", "Merhaba", "Türkçe karakter: çğıöşü")
em = email.message_from_bytes(base64.urlsafe_b64decode([c for c in calls if c[1].endswith("/messages/send")][-1][3]["raw"]), policy=policy.default)
check("yeni e-posta MIME (Türkçe)", em["To"] == "x@example.com" and "çğıöşü" in em.get_content())
check("taslak", "d1" in google.gmail_draft("y@example.com", "Konu", "Metin"))
check("arşivle", "uygulandı" in google.gmail_modify("m1,m2", "arşivle"))
check("etiket ekle (oluştur)", "uygulandı" in google.gmail_modify("m1", "label_add", "Faturalar"))
check("çöp kritik", tools.is_critical("gmail_modify", {"action": "trash"}) and not tools.is_critical("gmail_modify", {"action": "arşivle"}))
check("gönderme kritik", tools.is_critical("gmail_send", {}) and tools.is_critical("gmail_reply", {}))
check("takvim listele", google.calendar_events(1)[0]["başlık"] == "Dişçi")
r = google.calendar_create("Toplantı", "2026-11-06 10:00", duration_minutes=45)
ev = [c for c in calls if "/events" in c[1] and c[0] == "POST"][-1][3]
check("takvim oluştur (45 dk)", ev["start"]["dateTime"].startswith("2026-11-06T10:00") and ev["end"]["dateTime"].startswith("2026-11-06T10:45"))
check("katılımcılı etkinlik kritik", tools.is_critical("calendar_create", {"attendees": "a@b.com"}) and not tools.is_critical("calendar_create", {}))
fs = google.calendar_free_slots("2026-11-05", 9, 18)
check("boş zaman hesabı", isinstance(fs, list) and len(fs) >= 1, fs)
notes = []
google.TOKEN_FILE.write_text(json.dumps({"access_token": "x", "expires_at": time.time() + 999}))
google._last_mail_check[0] = 1  # ilk tur değilmiş gibi
google.watch_tick(lambda t: notes.append(t))
check("önemli e-posta bildirimi", any("Önemli yeni e-posta" in n for n in notes), notes)
google.TOKEN_FILE.unlink()

print("OFFICE")
tmp = Path(tempfile.mkdtemp())
r = office.create_word("Rapor", "# Giriş\nBu **önemli** bir rapor.\n- madde 1\n- madde 2\n| Ad | Puan |\n|---|---|\n| Ali | 90 |", str(tmp / "r.docx"))
import docx  # noqa: E402
d = docx.Document(str(tmp / "r.docx"))
check("Word: başlık, madde, tablo", "Giriş" in [p.text for p in d.paragraphs] and len(d.tables) == 1 and d.tables[0].cell(1, 1).text == "90")
r = office.create_excel("Ay,Satış,Gider\nOcak,100,60\nŞubat,150,70\nMart,120,65", str(tmp / "t.xlsx"), chart="bar")
import openpyxl  # noqa: E402
ws = openpyxl.load_workbook(tmp / "t.xlsx").active
check("Excel: veri, toplam formülü, grafik", ws["B2"].value == 100 and ws["B5"].value == "=SUM(B2:B4)" and len(ws._charts) == 1)
r = office.create_powerpoint("Sunum", "# Hedefler\n- Büyüme\n- Kalite\n# Plan\n- Q1\n- Q2", str(tmp / "s.pptx"))
from pptx import Presentation  # noqa: E402
check("PowerPoint: 3 slayt", len(Presentation(str(tmp / "s.pptx")).slides) == 3)
r = office.create_pdf("PDF Rapor", "# Bölüm\nÇalışma **özeti**.\n- a\n- b", str(tmp / "a.pdf"))
office.create_pdf("İkinci", "metin", str(tmp / "b.pdf"))
r = office.merge_pdfs(f"{tmp/'a.pdf'},{tmp/'b.pdf'}", str(tmp / "m.pdf"))
from pypdf import PdfReader  # noqa: E402
check("PDF oluştur + birleştir", len(PdfReader(str(tmp / "m.pdf")).pages) == 2)
check("PDF ayır", "1 sayfa" in office.split_pdf(str(tmp / "m.pdf"), "2", str(tmp / "p2.pdf")))
(tmp / "v.csv").write_text("Ürün,Adet\nA,5\nB,7\nA,3\n", encoding="utf-8")
a = office.analyze_data(str(tmp / "v.csv"))
check("veri analizi", a["sütun_özeti"]["Adet"]["toplam"] == 15)
check("grafik PNG", "kaydedildi" in office.make_chart(str(tmp / "v.csv"), "bar", "Adet", str(tmp / "g.png")) and (tmp / "g.png").stat().st_size > 1000)
(tmp / "x.txt").write_text("a\nb\nc", encoding="utf-8")
(tmp / "y.txt").write_text("a\nB\nc", encoding="utf-8")
check("dosya karşılaştır", "-b" in office.compare_files(str(tmp / "x.txt"), str(tmp / "y.txt"))["farklar"])

print("DOSYA / WINDOWS (platformdan bağımsız kısımlar)")
(tmp / "d1").mkdir()
(tmp / "d1" / "a.bin").write_bytes(b"x" * 200000)
(tmp / "d1" / "b.bin").write_bytes(b"x" * 200000)
(tmp / "d1" / "c.jpg").write_bytes(b"y" * 10)
dup = windows.find_duplicates(str(tmp / "d1"), 100)
check("yinelenen dosya", isinstance(dup, dict) and len(dup["gruplar"][0]["dosyalar"]) == 2)
check("klasör düzenleme önizleme", windows.organize_folder(str(tmp / "d1"), True)["plan"].get("Resimler") == 1)
check("klasör düzenleme kritik değil (önizleme) / kritik (uygula)",
      not tools.is_critical("organize_folder", {"dry_run": True}) and tools.is_critical("organize_folder", {"dry_run": False}))
z = windows.zip_files(str(tmp / "d1"), str(tmp / "d1.zip"))
check("zip + unzip", "Arşiv" in z and "Açıldı" in windows.unzip_file(str(tmp / "d1.zip"), str(tmp / "out")))
check("powershell enjeksiyon temizliği", windows._safe("x'; Remove-Item C:\\ -Recurse; '") == "x Remove-Item C:\\ -Recurse ")
check("şüpheli tarama çalışıyor", isinstance(windows.suspicious_check(), dict))

print("FİNANS (sahte piyasa)")
finance._quote = lambda s, rng="5d": {"sembol": s, "fiyat": {"GC=F": 2000.0, "USDTRY=X": 34.0}.get(s, 10.0), "para": "USD", "değişim_%": 1.0, "seri": [9.0, 10.0]}
g = finance.gold_prices()
check("gram altın hesabı", abs(g["gram_altın_tl"] - 2000 * 34 / 31.1035) < 0.01)
finance.set_budget("market", 1000)
finance.add_transaction(5000, "maaş", kind="gelir")
r = finance.add_transaction(900, "market", "haftalık")
check("bütçe uyarısı", "%90" in r or "Dikkat" in r, r)
rep = finance.finance_report()
check("aylık rapor", rep["gelir"] >= 5000 and rep["kategoriler"]["market"]["harcanan"] >= 900)
fired = []
finance.price_alert("altın", ">", 1500)
finance.check_alerts(lambda t: fired.append(t))
check("fiyat alarmı tetiklendi", fired and "GC=F" in fired[0])

print("OTOMASYON")
r = automation.schedule_task("test görevi", "daily", "23:59")
check("günlük görev", "kuruldu" in r)
t = {"kind": "weekly", "at": "09:00", "weekday": 0, "monthday": 1, "every_minutes": 60}
import datetime as dt  # noqa: E402
check("haftalık sonraki pazartesi", dt.datetime.fromtimestamp(automation._next_run(t)).weekday() == 0)
t = {"kind": "monthly", "at": "09:00", "weekday": 0, "monthday": 31, "every_minutes": 60}
check("aylık 31 (kısa ayları atlar)", dt.datetime.fromtimestamp(automation._next_run(t)).day == 31)
check("yapılacak ekle/listele", "eklendi" in automation.todo_add("Rapor yaz", "2020-01-01 10:00", "yüksek"))
lst = automation.todo_list()
check("geciken işaretlendi", any(x["text"] == "Rapor yaz" and x["gecikti"] for x in lst))
seen = []
automation.tick(lambda t, k="info": seen.append(t))
check("son tarih bildirimi", any("Rapor yaz" in s for s in seen))

print("AKILLI EV (sahte Home Assistant)")
ha_calls = []


def fake_ha(path, method="GET", body=None):
    ha_calls.append((path, method, body))
    if path == "states":
        return [{"entity_id": "light.salon", "state": "off", "attributes": {"friendly_name": "Salon Lambası"}},
                {"entity_id": "climate.klima", "state": "cool", "attributes": {"friendly_name": "Klima", "temperature": 22}}]
    return []


smarthome._ha = fake_ha
check("cihaz listele", smarthome.home_devices("ışık")[0]["id"] == "light.salon")
smarthome.home_control("salon lambası", "brightness", "40")
check("parlaklık servisi", ha_calls[-1] == ("services/light/turn_on", "POST", {"entity_id": "light.salon", "brightness_pct": 40}))
smarthome.home_control("klima", "temperature", "24")
check("klima sıcaklık", ha_calls[-1][0] == "services/climate/set_temperature" and ha_calls[-1][2]["temperature"] == 24.0)
check("kilit açma kritik", tools.is_critical("home_control", {"action": "unlock"}))

print("ARAÇ SEÇİMİ")
check("mail → google", "google" in tools.pick_groups("okunmamış maillerimi özetle"))
check("sunum → office", "office" in tools.pick_groups("bana bir sunum hazırla"))
check("saat → sadece çekirdek", tools.pick_groups("saat kaç") == {"core", "plugins", "semantic"})

print("SES KİMLİĞİ (yapay konuşmacılar)")
import numpy as np  # noqa: E402
from core.skills import voiceid  # noqa: E402


def speaker(f0, formants, seed):
    r = np.random.default_rng(seed); sr = 16000; t = np.arange(sr * 4) / sr
    f = f0 * (1 + 0.08 * np.sin(2 * np.pi * 0.7 * t + seed))
    ph = 2 * np.pi * np.cumsum(f) / sr
    src = sum(np.sin(k * ph) / k for k in range(1, 30)) * (np.sin(2 * np.pi * 3.5 * t + seed) > -.2)
    spec = np.fft.rfft(src); fr = np.fft.rfftfreq(len(t), 1 / sr)
    sig = np.fft.irfft(spec * sum(np.exp(-((fr - F) / B) ** 2) for F, B in formants), len(t))
    return voiceid.make_wav((sig / np.abs(sig).max() * 0.5 + 0.01 * r.standard_normal(len(t))).astype(np.float32))


A = [(700, 120), (1200, 150), (2600, 200)]; B = [(500, 100), (1700, 150), (2900, 200)]
for i in range(3):
    voiceid.enroll("Murat", speaker(115, A, i))
    voiceid.enroll("Ayşe", speaker(220, B, 10 + i))
r1, r2, r3 = voiceid.identify(speaker(118, A, 99)), voiceid.identify(speaker(215, B, 98)), voiceid.identify(speaker(165, [(400, 90), (2100, 150), (3200, 200)], 97))
check("sahibi tanındı", r1["known"] and r1["name"] == "Murat" and r1["owner"], r1)
check("ikinci kişi ayırt edildi", r2["known"] and r2["name"] == "Ayşe" and not r2["owner"], r2)
check("yabancı reddedildi", not r3["known"], r3)

print("ŞİFRE KASASI")
from core.skills import vault  # noqa: E402
vault.save_entry("GitHub", "murat", "Gizli!Şifre123")
check("şifreli saklama (düz metin yok)", "Gizli" not in vault.VAULT.read_text())
check("çözme", vault.reveal("GitHub") == "Gizli!Şifre123")
check("model sadece isim görür", "Gizli" not in json.dumps(vault.vault_list()))
check("kopyalama/yazma kritik", tools.is_critical("vault_copy", {}) and tools.is_critical("vault_type", {}))
check("şifre gücü", vault.password_check("GitHub")["puan_6_üzerinden"] >= 5)

print("ALIŞKANLIK / PANO")
from core.skills import habits  # noqa: E402
from core import memory  # noqa: E402
memory._q("INSERT INTO app_usage(day,app,minutes) VALUES(?,?,?)", (dt.date.today().isoformat(), "chrome", 90), commit=True)
memory._q("INSERT INTO app_usage(day,app,minutes) VALUES(?,?,?)", (dt.date.today().isoformat(), "Code", 30), commit=True)
u = habits.usage_report(1)
check("ekran süresi raporu", u["uygulamalar"][0]["uygulama"] == "chrome" and u["toplam_saat"] == 2.0)
memory._q("INSERT INTO clip_history(text,ts) VALUES(?,?)", ("kopyalanan metin", time.time()), commit=True)
check("pano geçmişi arama", habits.clipboard_history(5, "kopyalanan")[0]["metin"] == "kopyalanan metin")

print("OYUN")
from core.skills import games  # noqa: E402
acf = '"AppState"\n{\n\t"appid"\t\t"730"\n\t"name"\t\t"Counter-Strike 2"\n\t"installdir"\t\t"Counter-Strike Global Offensive"\n\t"SizeOnDisk"\t\t"35000000000"\n}'
g = games.parse_acf(acf)
check("Steam manifest okuma", g["ad"] == "Counter-Strike 2" and g["id"] == "730" and g["boyut_gb"] == 35.0)
check("kütüphane yolları", games._vdf_paths('"1"\n{\n"path"\t\t"D:\\\\SteamLibrary"\n}') == ["D:\\SteamLibrary"])
csv_txt = "Application,ProcessID,MsBetweenPresents\n" + "\n".join(f"cs2.exe,1,{x}" for x in [6.9] * 98 + [20, 25])
fps = games.parse_presentmon(csv_txt)
check("FPS hesabı", 130 < fps["ortalama_fps"] < 145 and fps["%1_düşük_fps"] < 60, fps)

print("KENDİNİ GELİŞTİRME")
from core.skills import selfdev  # noqa: E402
selfdev.PLUGINS = Path(tempfile.mkdtemp()); selfdev.STAGING = selfdev.PLUGINS / "_deneme"
import core.skills as sk  # noqa: E402
sk.ROOT = selfdev.PLUGINS.parent  # eklentileri geçici klasörden yükle
(selfdev.PLUGINS.parent / "plugins").mkdir(exist_ok=True)
selfdev.PLUGINS = selfdev.PLUGINS.parent / "plugins"; selfdev.STAGING = selfdev.PLUGINS / "_deneme"
bad = selfdev.create_plugin("bozuk", "def x(:\n  pass")
check("hatalı eklenti reddedildi", "BAŞARISIZ" in bad["durum"])
good = selfdev.create_plugin("selam", "def selam(ad='dünya'):\n    return 'Merhaba ' + ad\n\nTOOLS = {'selam_ver': (selam, {'description': 'selam verir', 'parameters': {'type': 'object', 'properties': {'ad': {'type': 'string'}}, 'required': []}}, False)}\n")
check("geçerli eklenti test edilip etkinleşti", "etkinleştirildi" in good["durum"] and "selam_ver" in tools.TOOLS, good)
check("yeni yetenek çalışıyor", tools.execute("selam_ver", {"ad": "Murat"}) == "Merhaba Murat")
check("eklenti yazma kritik", tools.is_critical("create_plugin", {}))
check("kod okuma sadece kendi klasörü", "Sadece" in selfdev.read_own_code("../../etc/passwd"))

print("ANLAMSAL HAFIZA")
from core.skills import semantic  # noqa: E402
memory.add_fact("Kullanıcının kızının adı Elif")
check("model yoksa kelime aramasına düşer", "Elif" in json.dumps(semantic.deep_recall("Elif"), ensure_ascii=False))
check("kosinüs", abs(semantic._cos([1, 0], [1, 0]) - 1) < 1e-6 and abs(semantic._cos([1, 0], [0, 1])) < 1e-6)

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
