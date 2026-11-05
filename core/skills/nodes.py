"""Çoklu bilgisayar yönetimi: ağdaki diğer JARVIS'leri (düğüm) bulma ve bağlama, durumlarını izleme, onlara dosya gönderme/alma,
uzaktan komut çalıştırma (karşı tarafın izniyle) ve çevrimdışı düğümler için görev kuyruğu.

Güvenlik: her düğüm 'python run.py --lan' ile ve erişim anahtarıyla (JARVIS_TOKEN) çalışır; anahtar olmadan hiçbir işlem yapılamaz.
Uzaktan komut kabulü alıcı bilgisayarda varsayılan KAPALIDIR (Ayarlar: allow_remote_commands). Kritik işlemler uzaktan gelse bile
alıcı bilgisayarda onay bekler; otomatik onaylanmaz."""
import concurrent.futures as cf
import ipaddress
import json
import platform
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .. import memory
from ..config import VERSION, load_settings
from ..tools import S, _path, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS nodes(name TEXT PRIMARY KEY, url TEXT, token TEXT, added REAL, last_seen REAL, info TEXT, fp TEXT);
CREATE TABLE IF NOT EXISTS node_queue(id INTEGER PRIMARY KEY AUTOINCREMENT, node TEXT, kind TEXT, payload TEXT, status TEXT, result TEXT,
    tries INTEGER DEFAULT 0, created REAL, done REAL);
""")


try:
    memory._q("ALTER TABLE nodes ADD COLUMN fp TEXT", commit=True)
except Exception:
    pass


# ---------------- bu düğümün kendi bilgisi (sunucu uç noktaları kullanır) ----------------

def hello():
    return {"jarvis": True, "name": socket.gethostname(), "version": VERSION, "os": platform.system()}


def self_info():
    from ..tools import system_status
    st = system_status()
    return {**hello(), "durum": st if isinstance(st, dict) else {}, "uzaktan_komut": bool(load_settings().get("allow_remote_commands")), "zaman": time.time()}


# ---------------- HTTP yardımcıları ----------------

def _req(node, path, body=None, raw=None, timeout=15, ctype="application/json"):
    """HTTP(S) isteği. https düğümler kendinden imzalı sertifika kullanır: ilk bağlantıda sertifika parmak izi kaydedilir,
    sonraki her bağlantıda aynı olmalıdır (TOFU sabitleme; araya giren sahte sunucuya anahtar gönderilmez)."""
    import hashlib
    import http.client
    import ssl
    u = urllib.parse.urlparse(node["url"].rstrip("/") + path)
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hdr = {"x-token": node.get("token") or "", "User-Agent": "JARVIS-node"}
    if data is not None:
        hdr["Content-Type"] = ctype
    if u.scheme == "https":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=timeout, context=ctx)
        conn.connect()
        fp = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
        want = node.get("fp")
        if want and want != fp:
            conn.close()
            raise RuntimeError("Sertifika parmak izi değişti! Araya giren biri olabilir; bağlantı kesildi (düğümü kaldırıp yeniden ekle).")
        node["_fp"] = fp
    else:
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    try:
        conn.request("POST" if data is not None else "GET", u.path + ("?" + u.query if u.query else ""), body=data, headers=hdr)
        r = conn.getresponse()
        b = r.read()
        if r.status >= 400:
            raise urllib.error.HTTPError(u.geturl(), r.status, r.reason, r.headers, None)
        return json.loads(b) if (r.getheader("Content-Type") or "").startswith("application/json") else b
    finally:
        conn.close()


def _node(name):
    r = memory._q("SELECT * FROM nodes WHERE name=? OR name LIKE ?", (name, f"%{name}%"), one=True)
    return dict(r) if r else None


def http_exc():
    import http.client
    return http.client.HTTPException


def _norm_url(u):
    u = u.strip()
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    p = urllib.parse.urlparse(u)
    if not p.port:
        u = f"{p.scheme}://{p.hostname}:8765"
    return u.rstrip("/")


# ---------------- araçlar ----------------

def node_add(url, token, name=""):
    """Başka bir JARVIS bilgisayarını bağlar. Karşıda 'python run.py --lan' açık olmalı; anahtar o bilgisayardaki ekranda/terminalde yazar."""
    u = _norm_url(url)
    n = {"url": u, "token": token.strip()}
    try:
        try:
            info = _req(n, "/api/node/info", timeout=6)
        except (ConnectionError, OSError, http_exc()) as first:
            if "://" in url or isinstance(first, urllib.error.HTTPError):
                raise
            n["url"] = u = u.replace("http://", "https://", 1)  # karşı taraf --https ile açılmış olabilir
            info = _req(n, "/api/node/info", timeout=6)
    except urllib.error.HTTPError as e:
        return "Anahtar yanlış (401)." if e.code == 401 else f"Bağlanılamadı: HTTP {e.code}"
    except Exception as e:
        return f"Bağlanılamadı ({u}): {e}. Karşı bilgisayarda 'python run.py --lan' açık mı, güvenlik duvarı 8765'e izin veriyor mu?"
    if not isinstance(info, dict) or not info.get("jarvis"):
        return "Bu adreste JARVIS yok."
    nm = name or info["name"]
    memory._q("INSERT OR REPLACE INTO nodes(name,url,token,added,last_seen,info,fp) VALUES(?,?,?,?,?,?,?)",
              (nm, u, n["token"], time.time(), time.time(), json.dumps(info, ensure_ascii=False), n.get("_fp")), commit=True)
    return {"bağlandı": nm, "adres": u, "sürüm": info.get("version"), "işletim_sistemi": info.get("os"), "uzaktan_komut_izni": info.get("uzaktan_komut")}


def node_remove(name):
    n = _node(name)
    if not n:
        return "Böyle bir düğüm yok."
    memory._q("DELETE FROM nodes WHERE name=?", (n["name"],), commit=True)
    return f"Bağlantı kaldırıldı: {n['name']}"


def _probe(n):
    t0 = time.time()
    try:
        info = _req(n, "/api/node/info", timeout=4)
        memory._q("UPDATE nodes SET last_seen=?, info=? WHERE name=?", (time.time(), json.dumps(info, ensure_ascii=False), n["name"]), commit=True)
        st = info.get("durum", {})
        return {"ad": n["name"], "çevrimiçi": True, "gecikme_ms": round((time.time() - t0) * 1000), "cpu": st.get("cpu_yüzde"), "ram": st.get("ram_yüzde"),
                "disk": st.get("disk_yüzde"), "pil": st.get("pil"), "uzaktan_komut": info.get("uzaktan_komut"), "adres": n["url"]}
    except Exception as e:
        return {"ad": n["name"], "çevrimiçi": False, "hata": str(e)[:80], "son_görülme": n["last_seen"], "adres": n["url"]}


def node_list():
    rows = [dict(r) for r in memory._q("SELECT * FROM nodes ORDER BY name")]
    if not rows:
        return "Bağlı başka bilgisayar yok. node_add ile ekle ya da node_discover ile ağı tara."
    with cf.ThreadPoolExecutor(8) as ex:
        return list(ex.map(_probe, rows))


def node_status(name):
    n = _node(name)
    if not n:
        return "Böyle bir düğüm yok."
    try:
        return _req(n, "/api/node/info", timeout=6)
    except Exception as e:
        return f"{n['name']} çevrimdışı: {e}"


def node_discover(subnet="", port=8765):
    """Yerel ağı (/24) tarar ve JARVIS çalışan bilgisayarları bulur (anahtar gerekmeyen 'merhaba' ucu ile)."""
    if not subnet:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "192.168.1.10"
        subnet = str(ipaddress.ip_network(ip + "/24", strict=False))
    net = ipaddress.ip_network(subnet, strict=False)
    if net.num_addresses > 1024:
        return "En fazla /22 ağ taranabilir."

    def hit(h):
        for sch in ("http", "https"):
            u = f"{sch}://{h}:{int(port)}"
            try:
                j = _req({"url": u, "token": ""}, "/api/node/hello", timeout=0.8)
                if isinstance(j, dict) and j.get("jarvis"):
                    return {"ad": j.get("name"), "adres": u, "sürüm": j.get("version"), "os": j.get("os")}
            except Exception:
                continue
        return None
    with cf.ThreadPoolExecutor(64) as ex:
        found = [x for x in ex.map(hit, [str(h) for h in net.hosts()]) if x]
    known = {r["url"] for r in memory._q("SELECT url FROM nodes")}
    for f in found:
        f["bağlı"] = f["adres"] in known
    return found or f"{subnet} ağında JARVIS bulunamadı (diğer bilgisayarlarda 'python run.py --lan' açık olmalı)."


def node_run(name, command, wait=True):
    """Diğer bilgisayarın JARVIS'ine doğal dilde komut gönderir (ör. 'tarayıcıyı kapat', 'disk durumunu söyle'). Çevrimdışıysa kuyruğa alınır."""
    n = _node(name)
    if not n:
        return "Böyle bir düğüm yok."
    try:
        r = _req(n, "/api/node/run", {"text": command, "from": socket.gethostname()}, timeout=180)
        return {"düğüm": n["name"], **r} if isinstance(r, dict) else r
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return f"{n['name']} uzaktan komut kabul etmiyor (o bilgisayarda Ayarlar > Bağlantılar > 'Uzaktan komutlara izin ver' açılmalı)."
        return f"Hata: HTTP {e.code}"
    except Exception as e:
        if str(wait).lower() in ("true", "1"):
            qid = memory._q("INSERT INTO node_queue(node,kind,payload,status,created) VALUES(?,?,?,?,?)",
                            (n["name"], "run", json.dumps({"text": command}, ensure_ascii=False), "bekliyor", time.time()), commit=True)
            return f"{n['name']} şu an ulaşılamıyor ({str(e)[:60]}). Komut kuyruğa alındı (#{qid}); bilgisayar açılınca otomatik gönderilecek."
        return f"Ulaşılamadı: {e}"


def node_broadcast(command):
    """Aynı komutu tüm bağlı bilgisayarlara paralel gönderir."""
    rows = [dict(r) for r in memory._q("SELECT * FROM nodes")]
    if not rows:
        return "Bağlı düğüm yok."
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda n: node_run(n["name"], command), rows))
    return res


def node_send_file(name, path, folder="indirilenler"):
    n = _node(name)
    if not n:
        return "Böyle bir düğüm yok."
    p = _path(path)
    if not p.is_file():
        return f"Dosya yok: {p}"
    if p.stat().st_size > 500_000_000:
        return "500 MB'tan büyük dosyalar için bulut/USB kullan."
    q = urllib.parse.urlencode({"path": folder, "name": p.name})
    try:
        r = _req(n, f"/api/files/upload?{q}", raw=p.read_bytes(), timeout=600, ctype="application/octet-stream")
        return {"gönderildi": p.name, "düğüm": n["name"], "hedef": r.get("path") if isinstance(r, dict) else ""}
    except Exception as e:
        qid = memory._q("INSERT INTO node_queue(node,kind,payload,status,created) VALUES(?,?,?,?,?)",
                        (n["name"], "file", json.dumps({"path": str(p), "folder": folder}, ensure_ascii=False), "bekliyor", time.time()), commit=True)
        return f"Gönderilemedi ({str(e)[:60]}); kuyruğa alındı (#{qid})."


def node_get_file(name, remote_path, folder="indirilenler"):
    n = _node(name)
    if not n:
        return "Böyle bir düğüm yok."
    try:
        data = _req(n, "/api/files/download?" + urllib.parse.urlencode({"path": remote_path}), timeout=600)
    except Exception as e:
        return f"Alınamadı: {e}"
    if isinstance(data, dict):
        return f"Alınamadı: {data.get('error')}"
    out = _path(folder) / (Path(remote_path.replace("\\", "/")).name or "dosya")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return {"alındı": str(out), "boyut_KB": round(len(data) / 1024, 1), "düğüm": n["name"]}


def node_files(name, path=""):
    n = _node(name)
    if not n:
        return "Böyle bir düğüm yok."
    try:
        return _req(n, "/api/files/list?" + urllib.parse.urlencode({"path": path}), timeout=15)
    except Exception as e:
        return f"Listelenemedi: {e}"


def node_queue_list():
    rows = memory._q("SELECT * FROM node_queue ORDER BY id DESC LIMIT 30")
    return [{"no": r["id"], "düğüm": r["node"], "tür": r["kind"], "iş": json.loads(r["payload"]).get("text") or json.loads(r["payload"]).get("path"),
             "durum": r["status"], "deneme": r["tries"], "sonuç": (r["result"] or "")[:200]} for r in rows] or "Kuyruk boş."


def queue_tick():
    """Zamanlayıcı çağırır: düğümlerin durumunu yoklar, bekleyen kuyruk işlerini düğüm çevrimiçi olunca gönderir."""
    nodes = [dict(r) for r in memory._q("SELECT * FROM nodes")]
    if nodes:
        with cf.ThreadPoolExecutor(8) as ex:
            list(ex.map(_probe, nodes))
    rows = memory._q("SELECT * FROM node_queue WHERE status='bekliyor' AND tries<200 ORDER BY id LIMIT 10")
    for r in rows:
        n = _node(r["node"])
        if not n:
            memory._q("UPDATE node_queue SET status='iptal', result='düğüm silindi' WHERE id=?", (r["id"],), commit=True)
            continue
        p = json.loads(r["payload"])
        try:
            if r["kind"] == "run":
                res = _req(n, "/api/node/run", {"text": p["text"], "from": socket.gethostname()}, timeout=180)
            else:
                f = Path(p["path"])
                res = _req(n, "/api/files/upload?" + urllib.parse.urlencode({"path": p["folder"], "name": f.name}), raw=f.read_bytes(), timeout=600,
                           ctype="application/octet-stream")
            memory._q("UPDATE node_queue SET status='gönderildi', result=?, done=?, tries=tries+1 WHERE id=?",
                      (json.dumps(res, ensure_ascii=False)[:2000], time.time(), r["id"]), commit=True)
            memory.notify(f"Kuyruktaki iş {n['name']} bilgisayarına iletildi: {p.get('text') or Path(p.get('path', '')).name}", "info")
        except urllib.error.HTTPError as e:
            memory._q("UPDATE node_queue SET status='reddedildi', result=?, tries=tries+1 WHERE id=?", (f"HTTP {e.code}", r["id"]), commit=True)
        except Exception:
            memory._q("UPDATE node_queue SET tries=tries+1 WHERE id=?", (r["id"],), commit=True)


def handle_remote_run(text, sender=""):
    """Sunucu: başka bir JARVIS'ten gelen komutu bu bilgisayarda çalıştırır (izin açıksa)."""
    from .. import brain
    if not load_settings().get("allow_remote_commands"):
        return None
    memory.notify(f"Uzak komut ({sender or 'başka bilgisayar'}): {text}", "info")
    out, confirms, meta = brain.collect(brain.chat(f"[Uzak bilgisayardan ({sender}) komut] {text}", session="remote", source="remote", hidden=False))
    return {"cevap": out, "onay_bekleyen": [c["text"] for c in confirms], "not": "Kritik işlemler bu bilgisayarda onay bekliyor." if confirms else ""}


TOOLS = {
    "node_add": (node_add, _schema("Ağdaki başka bir JARVIS bilgisayarını bağlar (adres + erişim anahtarı).", {"url": S("IP ya da adres (ör. 192.168.1.20)"), "token": S("o bilgisayarın JARVIS_TOKEN'ı"), "name": S("takma ad")}, ["url", "token"]), False),
    "node_list": (node_list, _schema("Bağlı tüm bilgisayarları canlı durumlarıyla (çevrimiçi, CPU, RAM, disk, pil) listeler.", {}), False),
    "node_status": (node_status, _schema("Bir bilgisayarın ayrıntılı durumu.", {"name": S("ad")}, ["name"]), False),
    "node_discover": (node_discover, _schema("Yerel ağı tarayıp JARVIS çalışan bilgisayarları bulur.", {"subnet": S("ör. 192.168.1.0/24 (boş: otomatik)")}), False),
    "node_run": (node_run, _schema("Başka bilgisayardaki JARVIS'e komut gönderir; çevrimdışıysa kuyruğa alır.", {"name": S("bilgisayar"), "command": S("komut")}, ["name", "command"]), True),
    "node_broadcast": (node_broadcast, _schema("Aynı komutu tüm bağlı bilgisayarlara gönderir.", {"command": S("komut")}, ["command"]), True),
    "node_send_file": (node_send_file, _schema("Dosyayı başka bilgisayara gönderir.", {"name": S("bilgisayar"), "path": S("dosya"), "folder": S("hedef klasör (indirilenler)")}, ["name", "path"]), False),
    "node_get_file": (node_get_file, _schema("Başka bilgisayardan dosya alır.", {"name": S("bilgisayar"), "remote_path": S("oradaki dosya yolu"), "folder": S("buraya kaydedilecek klasör")}, ["name", "remote_path"]), False),
    "node_files": (node_files, _schema("Başka bilgisayardaki klasörü listeler.", {"name": S("bilgisayar"), "path": S("klasör")}, ["name"]), False),
    "node_remove": (node_remove, _schema("Bilgisayar bağlantısını kaldırır.", {"name": S("ad")}, ["name"]), False),
    "node_queue_list": (node_queue_list, _schema("Uzak bilgisayarlar için bekleyen/gönderilen işler kuyruğu.", {}), False),
}
