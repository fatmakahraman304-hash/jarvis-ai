"""Çoklu bilgisayar testi: iki gerçek JARVIS sunucusu (A bu süreç, B ayrı süreç) arasında bağlanma, anahtar kontrolü,
izin kontrolü, uzaktan komut, dosya gönder/al ve çevrimdışı kuyruk. Çalıştır: python tests/test_nodes.py"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_nodeA_")
HOME_B, DATA_B = tempfile.mkdtemp(prefix="jv_homeB_"), tempfile.mkdtemp(prefix="jv_nodeB_")
ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


IP = lan_ip()
FP, BP = free_port(), free_port()
fake = subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_llm.py"), str(FP)])
envB = dict(os.environ, JARVIS_DATA=DATA_B, HOME=HOME_B, USERPROFILE=HOME_B, JARVIS_TOKEN="gizli-anahtar", CUSTOM_BASE_URL=f"http://127.0.0.1:{FP}")


def startB():
    p = subprocess.Popen([sys.executable, "run.py", "--lan", "--no-browser", "--port", str(BP)], cwd=ROOT, env=envB, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{BP}/api/node/hello", timeout=1); return p
        except Exception:
            time.sleep(0.25)
    return p


os.environ["CUSTOM_BASE_URL"] = f"http://127.0.0.1:{FP}"
B = startB()
try:
    from core.skills import nodes as nd
    print("BAĞLANTI" + ("" if IP != "127.0.0.1" else "  (yalnızca loopback: anahtar kontrolü atlanır)"))
    if IP != "127.0.0.1":
        check("yanlış anahtar reddedilir", nd.node_add(f"{IP}:{BP}", "yanlis") == "Anahtar yanlış (401).")
    r = nd.node_add(f"{IP}:{BP}", "gizli-anahtar", "ofis")
    check("doğru anahtarla bağlandı", isinstance(r, dict) and r["bağlandı"] == "ofis" and r["uzaktan_komut_izni"] is False, r)
    ls = nd.node_list()
    check("canlı durum (çevrimiçi, RAM)", ls[0]["çevrimiçi"] and ls[0]["ram"] is not None, ls)
    if IP != "127.0.0.1":
        net = IP.rsplit(".", 1)[0] + ".0/24"
        d = nd.node_discover(net, BP)
        check("ağ taraması JARVIS'i buldu", isinstance(d, list) and any(x["adres"].endswith(f":{BP}") and x["bağlı"] for x in d), d)
    print("UZAKTAN KOMUT")
    check("izin kapalıyken reddedilir", "kabul etmiyor" in str(nd.node_run("ofis", "saat kaç")))
    if IP != "127.0.0.1":
        rq = urllib.request.Request(f"http://{IP}:{BP}/api/settings", data=json.dumps({"allow_remote_commands": True}).encode(),
                                    headers={"Content-Type": "application/json", "x-token": "gizli-anahtar"}, method="POST")
        urllib.request.urlopen(rq).read()
        check("uzaktan izin açma engellendi (anahtar olsa bile)", "kabul etmiyor" in str(nd.node_run("ofis", "saat kaç")))
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{BP}/api/settings", data=json.dumps({"allow_remote_commands": True}).encode(),
                                                  headers={"Content-Type": "application/json"}, method="POST")).read()
    r = nd.node_run("ofis", "saat kaç")
    check("izin açıkken komut karşıda çalıştı", isinstance(r, dict) and r["düğüm"] == "ofis" and "Tamam" in r["cevap"], r)
    print("DOSYA")
    src = Path(tempfile.mkdtemp()) / "rapor.txt"; src.write_text("gizli olmayan rapor", encoding="utf-8")
    s = nd.node_send_file("ofis", str(src))
    check("dosya gönderildi", isinstance(s, dict) and Path(s["hedef"]).read_text(encoding="utf-8") == "gizli olmayan rapor", s)
    back = Path(tempfile.mkdtemp())
    g = nd.node_get_file("ofis", s["hedef"], str(back))
    check("dosya geri alındı", isinstance(g, dict) and (back / "rapor.txt").read_text(encoding="utf-8") == "gizli olmayan rapor", g)
    check("uzak klasör listesi", "rapor.txt" in json.dumps(nd.node_files("ofis", str(Path(s["hedef"]).parent)), ensure_ascii=False))
    print("ÇEVRİMDIŞI KUYRUK")
    B.terminate(); B.wait(5)
    q = nd.node_run("ofis", "saat kaç")
    check("çevrimdışı → kuyruğa alındı", "kuyruğa alındı" in q, q)
    check("liste çevrimdışı gösterir", nd.node_list()[0]["çevrimiçi"] is False)
    nd.queue_tick()
    check("kapalıyken kuyrukta bekler", nd.node_queue_list()[0]["durum"] == "bekliyor")
    B = startB()
    nd.queue_tick()
    ql = nd.node_queue_list()[0]
    check("açılınca kuyruktaki iş gönderildi", ql["durum"] == "gönderildi" and "Tamam" in ql["sonuç"], ql)
    check("bağlantı kaldır", nd.node_remove("ofis").startswith("Bağlantı kaldırıldı") and isinstance(nd.node_list(), str))
    print("ŞİFRELİ (HTTPS) DÜĞÜM")
    B.terminate(); B.wait(5)
    B = subprocess.Popen([sys.executable, "run.py", "--lan", "--https", "--no-browser", "--port", str(BP)], cwd=ROOT, env=envB, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            nd._req({"url": f"https://127.0.0.1:{BP}", "token": ""}, "/api/node/hello", timeout=1); break
        except Exception:
            time.sleep(0.25)
    r = nd.node_add(f"{IP}:{BP}", "gizli-anahtar", "https-ofis")
    check("http denenip https'e otomatik geçildi", isinstance(r, dict) and r["adres"].startswith("https://"), r)
    fp = nd._node("https-ofis")["fp"]
    check("sertifika parmak izi kaydedildi (TOFU)", fp and len(fp) == 64)
    check("şifreli bağlantıda komut çalışır", "Tamam" in nd.node_run("https-ofis", "saat kaç")["cevap"])
    nd.memory._q("UPDATE nodes SET fp=? WHERE name=?", ("0" * 64, "https-ofis"), commit=True)
    check("parmak izi değişirse bağlantı reddedilir", "parmak izi değişti" in str(nd.node_status("https-ofis")))
finally:
    B.terminate(); fake.terminate()

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
