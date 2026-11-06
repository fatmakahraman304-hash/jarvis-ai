"""Tek tuşla güncelleme testi: geçici bir JARVIS kurulumu sahte GitHub'dan yeni sürümü indirir, test eder, kurar ve
gözetmen sayesinde aynı süreçte yeniden başlar. .env, data/ ve kullanıcı eklentisi korunmalı; testi geçmeyen sürüm uygulanmamalı.
Çalıştır: python tests/test_update.py"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_updt_")
ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


def copy_code(dst):
    def ign(d, names):
        rel = os.path.relpath(d, ROOT)
        return {n for n in names if n in (".venv", "__pycache__", ".git", "node_modules", ".env") or n.endswith(".pyc") or (rel == "." and n == "data")}
    shutil.copytree(ROOT, dst, ignore=ign)


def make_zip(src, version, broken=False):
    tmp = Path(tempfile.mkdtemp()) / "repo-abc123"
    copy_code(tmp)
    cfg = tmp / "core" / "config.py"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(f'VERSION = "{src}"', f'VERSION = "{version}"'), encoding="utf-8")
    (tmp / "version.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    (tmp / "core" / "yeni_modul.py").write_text("X = 1\n", encoding="utf-8")
    if broken:
        (tmp / "core" / "brain.py").write_text("bozuk kod (\n", encoding="utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p in tmp.rglob("*"):
            if p.is_file():
                z.write(p, "repo-abc123/" + p.relative_to(tmp).as_posix())
    return buf.getvalue()


REMOTE = {"version": None, "zip": b""}


class GH(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/repos/test/jarvis/contents/version.json"):
            b = json.dumps({"version": REMOTE["version"], "notes": ["test notu"], "date": "2026-11-05"}).encode()
        elif self.path.startswith("/repos/test/jarvis/zipball/"):
            b = REMOTE["zip"]
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.end_headers(); self.wfile.write(b)


def port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


gh = ThreadingHTTPServer(("127.0.0.1", 0), GH)
threading.Thread(target=gh.serve_forever, daemon=True).start()
from core.config import VERSION as CUR  # noqa: E402

inst = Path(tempfile.mkdtemp()) / "JARVIS"
copy_code(inst)
(inst / ".env").write_text(f"UPDATE_REPO=test/jarvis\nUPDATE_API=http://127.0.0.1:{gh.server_address[1]}\nGEMINI_API_KEY=benim-anahtarim\n", encoding="utf-8")
(inst / "data").mkdir(exist_ok=True)
(inst / "data" / "hafiza_izi.txt").write_text("hafızam", encoding="utf-8")
(inst / "plugins" / "benim_eklentim.py").write_text("TOOLS = {}\n", encoding="utf-8")
(inst / "core" / "eski_dosya.py").write_text("# kaldırılacak\n", encoding="utf-8")
P = port()
envv = {k: v for k, v in os.environ.items() if k not in ("JARVIS_DATA", "UPDATE_REPO", "UPDATE_API")}
proc = subprocess.Popen([sys.executable, "run.py", "--no-browser", "--port", str(P)], cwd=inst, env=envv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def api(path, body=None, timeout=900):
    req = urllib.request.Request(f"http://127.0.0.1:{P}{path}", data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def wait_up(t=60):
    for _ in range(int(t * 4)):
        try:
            return api("/api/state", timeout=2)
        except Exception:
            time.sleep(0.25)


try:
    print("GÜNCELLEME")
    check("JARVIS açıldı", wait_up() is not None)
    REMOTE["version"] = CUR
    check("güncelken 'yeni yok'", api("/api/update?force=1")["yeni_var"] is False)
    major, minor, patch = (int(x) for x in CUR.split("."))
    bad = f"{major}.{minor}.{patch + 1}"
    REMOTE.update({"version": bad, "zip": make_zip(CUR, bad, broken=True)})
    r = api("/api/update", {"action": "apply"})
    check("testi geçmeyen sürüm UYGULANMADI", r["durum"] == "hata" and "testleri geçmedi" in r["hata"] and (inst / "core" / "eski_dosya.py").exists(), r)
    check("mevcut sürüm aynen çalışıyor", api("/api/state")["version"] == CUR)
    good = f"{major}.{minor}.{patch + 2}"
    REMOTE.update({"version": good, "zip": make_zip(CUR, good)})
    info = api("/api/update?force=1")
    check("yeni sürüm görüldü + notlar", info["yeni_var"] and info["uzak"] == good and info["notlar"] == ["test notu"], info)
    r = api("/api/update", {"action": "apply"})
    check("güncellendi", r["durum"] == "güncellendi" and r["yeni"] == good, r)
    time.sleep(3)
    st = wait_up(90)
    check("kendiliğinden yeniden başladı, yeni sürümde", st is not None and st["version"] == good, st and st.get("version"))
    check(".env korundu", "benim-anahtarim" in (inst / ".env").read_text(encoding="utf-8"))
    check("hafıza (data/) korundu", (inst / "data" / "hafiza_izi.txt").read_text(encoding="utf-8") == "hafızam")
    check("kendi eklentin korundu", (inst / "plugins" / "benim_eklentim.py").exists())
    check("yeni dosya geldi, kaldırılan eski dosya silindi", (inst / "core" / "yeni_modul.py").exists() and not (inst / "core" / "eski_dosya.py").exists())
    check("tek klasör: yanında yeni kopya/zip yok", sorted(p.name for p in inst.parent.iterdir()) == ["JARVIS"])
    bks = list((inst / "data" / "kod_yedekleri").glob("*.zip"))
    check("eski sürüm yedeklendi", len(bks) == 1 and bks[0].name.startswith(f"v{CUR}_"))
    r = api("/api/update", {"action": "rollback"})
    time.sleep(3)
    st = wait_up(90)
    check("önceki sürüme geri dönüş", st is not None and st["version"] == CUR and (inst / "core" / "eski_dosya.py").exists(), st and st.get("version"))
finally:
    proc.terminate()
    try:
        proc.wait(10)
    except Exception:
        proc.kill()
    # gözetmen öldüyse alt süreci de kapat
    try:
        import psutil
        for p in psutil.process_iter(["cmdline"]):
            c = p.info["cmdline"] or []
            if "--child" in c and str(P) in c:
                p.kill()
    except Exception:
        pass
    gh.shutdown()

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
