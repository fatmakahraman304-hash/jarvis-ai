"""Tek tuşla güncelleme (git gerektirmez).

Akış: GitHub'daki depodan version.json okunur → yeni sürüm varsa kod zip olarak indirilir → mevcut kod yedeklenir
(data/kod_yedekleri) → yeni dosyalar kopyalanır (.env, data/, .venv/ ve senin eklentilerin KORUNUR) → paket listesi
değiştiyse yeni paketler kurulur → yeni sürümün testleri çalışır → geçmezse otomatik olarak eski sürüme dönülür →
geçerse JARVIS kendini yeniden başlatır. Hiçbir yeni klasör/zip kopyası bırakmaz; tek klasör yerinde güncellenir.

Ayar (.env): UPDATE_REPO=kullanıcı/depo  · UPDATE_BRANCH=main  · GITHUB_TOKEN=(özel depo için salt-okunur anahtar)
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from .config import DATA, ROOT, VERSION, env

DEFAULT_REPO = "fatmakahraman304-hash/jarvis-ai"
KEEP = {".env", "data", ".venv", ".git", "__pycache__", "node_modules"}   # asla dokunulmaz
USER_DIRS = {"plugins"}                                                  # yalnızca güncellemedeki dosyalar eklenir, seninkiler silinmez
CODE_DIRS = {"core", "web", "tests", "tools", "arduino"}                 # güncellemede olmayan eski dosyalar buradan temizlenir
BACKUPS = DATA / "kod_yedekleri"
STATE = {"durum": "hazır", "adım": "", "ilerleme": 0, "hata": "", "son_kontrol": 0, "uzak": None}
_lock = threading.Lock()


def _ver(v):
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def _api():
    return (env("UPDATE_API") or "https://api.github.com").rstrip("/")


def _repo():
    return (env("UPDATE_REPO") or DEFAULT_REPO).strip().strip("/"), (env("UPDATE_BRANCH") or "main").strip()


def _get(url, timeout=30, accept="application/vnd.github+json"):
    hdr = {"User-Agent": "JARVIS-updater", "Accept": accept}
    tok = env("GITHUB_TOKEN")
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
        _log(f"Geçici indirme hatası; yeniden deneme {attempt + 2}/3")
        time.sleep(attempt + 1)


def _log(msg):
    try:
        with open(DATA / "guncelleme.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def check(force=False):
    """Uzak sürümü okur. {'yerel','uzak','yeni_var','notlar'}"""
    if not force and STATE["uzak"] and time.time() - STATE["son_kontrol"] < 600:
        u = STATE["uzak"]
    else:
        repo, br = _repo()
        try:
            raw = _get(f"{_api()}/repos/{repo}/contents/version.json?ref={br}", accept="application/vnd.github.raw+json")
            u = json.loads(raw)
        except urllib.error.HTTPError as e:
            msg = {401: "GitHub anahtarı geçersiz.", 403: "GitHub erişimi reddedildi/limit doldu.",
                   404: "Güncelleme deposu bulunamadı (özel depoysa .env'e GITHUB_TOKEN ekle)."}.get(e.code, f"HTTP {e.code}")
            return {"yerel": VERSION, "hata": msg}
        except Exception as e:
            return {"yerel": VERSION, "hata": f"İnternete/GitHub'a ulaşılamadı: {e}"}
        STATE.update({"uzak": u, "son_kontrol": time.time()})
    newer = _ver(u.get("version")) > _ver(VERSION)
    return {"yerel": VERSION, "uzak": u.get("version"), "yeni_var": newer, "notlar": u.get("notes", []), "tarih": u.get("date", "")}


def _files(base):
    out = set()
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if p.is_file() and not (set(rel.parts) & KEEP) and not p.name.endswith(".pyc"):
            out.add(rel.as_posix())
    return out


def backup():
    BACKUPS.mkdir(parents=True, exist_ok=True)
    f = BACKUPS / f"v{VERSION}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(_files(ROOT)):
            z.write(ROOT / rel, rel)
    olds = sorted(BACKUPS.glob("v*.zip"), key=lambda p: p.stat().st_mtime)
    for o in olds[:-5]:  # son 5 yedek yeter
        o.unlink(missing_ok=True)
    return f


def restore(zip_path):
    zp = Path(zip_path)
    with zipfile.ZipFile(zp) as z:
        names = set(z.namelist())
        for rel in _files(ROOT):
            top = rel.split("/")[0]
            if rel not in names and top in CODE_DIRS:
                (ROOT / rel).unlink(missing_ok=True)
        z.extractall(ROOT)
    return f"Geri yüklendi: {zp.name}"


def _pip(lines, log):
    py = sys.executable
    for spec in lines:
        for attempt in range(2):
            STATE["adım"] = f"Paket kuruluyor: {spec} (deneme {attempt+1}/2)"
            try:
                r = subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "--timeout", "15", "--retries", "2", "-q", spec], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
                if r.returncode == 0:
                    log.append(f"pip {spec}: tamam")
                    break
                detail = (r.stderr or r.stdout or "").strip()[-500:]
                transient = any(word in detail.lower() for word in ("timeout", "timed out", "connection", "temporary failure", "network", "503", "502"))
            except subprocess.TimeoutExpired:
                detail, transient = "Paket kurulumu 180 saniyeyi aştı.", True
            if not transient or attempt == 1:
                log.append(f"pip {spec}: kurulamadı")
                raise RuntimeError(f"Gerekli paket kurulamadı: {spec}. {detail}")
            _log(f"Paket ağı yeniden deneniyor: {spec}")
            time.sleep(1)


def _req_lines(p):
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.split("#", 1)[0].strip()
        if ln:
            out.append(ln)
    return out


def _tests(base):
    """Kısa, çevrimdışı güncelleme kontrolleri; entegrasyon testi CI üzerinde çalıştırılır."""
    tmp = tempfile.mkdtemp(prefix="jv_upd_")
    envv = dict(os.environ, JARVIS_DATA=tmp, PYTHONIOENCODING="utf-8")
    # Smoke test yerel sunucular başlatır ve normal açılış testidir; kullanıcı cihazındaki
    # güncelleme akışını dakikalarca bloke etmemesi için GitHub Actions'a bırakılır.
    tests = (
        "test_fast_conversation.py",
        "test_model_tiers.py",
        "test_models.py",
        "test_windows_transport.py",
        "test_research_budget.py",
        "test_live_voice.py",
    )
    total_timeout = 90
    per_test_timeout = 25
    deadline = time.monotonic() + total_timeout
    try:
        selected = [t for t in tests if (base / "tests" / t).is_file()]
        total = len(selected)
        if not total:
            return False, "Güncelleme paketi doğrulama testi içermiyor; güvenlik için uygulanmadı."
        for index, name in enumerate(selected, 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False, f"Toplam test süresi {total_timeout} saniyeyi aştı; güncelleme uygulanmadı."
            timeout = max(1, min(per_test_timeout, int(remaining)))
            progress = 35 + int(17 * (index - 1) / total)
            STATE.update({
                "ilerleme": progress,
                "adım": f"hızlı kontroller ({index}/{total}): {name}",
            })
            _log(f"Güncelleme testi başladı: {name} (zaman sınırı {timeout} sn)")
            try:
                result = subprocess.run(
                    [sys.executable, str(base / "tests" / name)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="ignore",
                    env=envv,
                    cwd=str(base),
                )
            except subprocess.TimeoutExpired:
                return False, f"{name} testi {timeout} saniyede tamamlanmadı; güncelleme uygulanmadı."
            if result.returncode != 0:
                detail = (result.stdout or "") + (result.stderr or "")
                return False, f"{name} testi başarısız; güncelleme uygulanmadı.\n{detail[-1500:]}"
            STATE.update({"ilerleme": 35 + int(17 * index / total)})
            _log(f"Güncelleme testi tamamlandı: {name}")
        STATE.update({"ilerleme": 52, "adım": "hızlı kontroller tamamlandı"})
        return True, ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def apply(restart=True):
    """İndir → yedekle → kopyala → paket kur → test → (başarısızsa geri dön) → yeniden başlat."""
    if not _lock.acquire(blocking=False):
        return {"durum": "zaten güncelleniyor"}
    log = []
    work = None
    try:
        STATE.update({"durum": "çalışıyor", "hata": "", "ilerleme": 5, "adım": "sürüm kontrol ediliyor"})
        info = check(force=True)
        if info.get("hata"):
            raise RuntimeError(info["hata"])
        if not info["yeni_var"]:
            STATE.update({"durum": "hazır", "ilerleme": 100, "adım": "zaten güncel"})
            return {"durum": "Zaten en yeni sürüm.", "sürüm": VERSION}
        repo, br = _repo()
        STATE.update({"ilerleme": 15, "adım": f"v{info['uzak']} indiriliyor"})
        data = _get(f"{_api()}/repos/{repo}/zipball/{br}", timeout=300, accept="application/vnd.github+json")
        work = Path(tempfile.mkdtemp(prefix="jv_new_"))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(work)
        roots = [p for p in work.iterdir() if p.is_dir()]
        new = roots[0] if len(roots) == 1 else work
        if (new / "JARVIS" / "run.py").exists():
            new = new / "JARVIS"
        if not (new / "run.py").exists() or not (new / "core").is_dir():
            raise RuntimeError("İndirilen paket geçerli bir JARVIS değil.")
        try:
            package_info = json.loads((new / "version.json").read_text(encoding="utf-8"))
            package_version = package_info.get("version")
        except (OSError, ValueError, AttributeError) as exc:
            raise RuntimeError("İndirilen paketin sürüm bilgisi okunamadı; güncelleme uygulanmadı.") from exc
        if package_version != info["uzak"]:
            raise RuntimeError(
                "İndirilen paket kontrol edilen sürümle eşleşmiyor; güncelleme uygulanmadı. "
                "Güncellemeyi yeniden kontrol edip tekrar dene."
            )
        STATE.update({"ilerleme": 35, "adım": "yeni sürüm test ediliyor"})
        ok, out = _tests(new)
        if not ok:
            raise RuntimeError("Yeni sürümün testleri geçmedi, güncelleme UYGULANMADI (mevcut sürüm aynen duruyor).\n" + out[-600:])
        STATE.update({"ilerleme": 55, "adım": "mevcut sürüm yedekleniyor"})
        bk = backup()
        old_req = _req_lines(ROOT / "requirements.txt") + _req_lines(ROOT / "requirements-extra.txt")
        try:
            STATE.update({"ilerleme": 65, "adım": "dosyalar güncelleniyor"})
            new_files = _files(new)
            for rel in sorted(new_files):
                dst = ROOT / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(new / rel, dst)
            for rel in _files(ROOT) - new_files:  # kaldırılmış eski kod dosyaları (eklentilerin ve verin korunur)
                if rel.split("/")[0] in CODE_DIRS:
                    (ROOT / rel).unlink(missing_ok=True)
            new_req = _req_lines(ROOT / "requirements.txt") + _req_lines(ROOT / "requirements-extra.txt")
            added = [r for r in new_req if r not in old_req]
            if added:
                STATE.update({"ilerleme": 80, "adım": "yeni paketler kuruluyor"})
                _pip(added, log)
        except Exception:
            restore(bk)
            raise
        shutil.rmtree(work, ignore_errors=True)
        _log(f"v{VERSION} → v{info['uzak']} kuruldu. {' | '.join(log)}")
        STATE.update({"durum": "bitti", "ilerleme": 100, "adım": f"v{info['uzak']} kuruldu, yeniden başlatılıyor"})
        try:
            from . import memory
            memory.notify(f"JARVIS v{info['uzak']} sürümüne güncellendi. " + " · ".join(info.get("notlar", [])[:5]), "info")
        except Exception:
            pass
        if restart:
            threading.Timer(1.5, lambda: os._exit(42)).start()  # run.py gözetmeni 42 koduyla yeniden başlatır
        return {"durum": "güncellendi", "önceki": VERSION, "yeni": info["uzak"], "yedek": bk.name, "notlar": info.get("notlar", []), "paketler": log}
    except Exception as e:
        STATE.update({"durum": "hata", "hata": str(e), "ilerleme": 0})
        _log(f"HATA: {e}")
        return {"durum": "hata", "hata": str(e)}
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        _lock.release()


def rollback():
    """En son yedeğe döner ve yeniden başlar."""
    olds = sorted(BACKUPS.glob("v*.zip"), key=lambda p: p.stat().st_mtime) if BACKUPS.exists() else []
    if not olds:
        return {"durum": "hata", "hata": "Geri dönülecek yedek yok."}
    msg = restore(olds[-1])
    threading.Timer(1.5, lambda: os._exit(42)).start()
    return {"durum": "geri alındı", "mesaj": msg}


def list_backups():
    return [p.name for p in sorted(BACKUPS.glob("v*.zip"), key=lambda p: -p.stat().st_mtime)] if BACKUPS.exists() else []


def auto_check_tick(notify):
    """Zamanlayıcı: günde bir kez kontrol, yeni sürüm varsa bildirir."""
    last = STATE.get("_bildirildi")
    if time.time() - STATE["son_kontrol"] < 6 * 3600 and STATE["son_kontrol"]:
        return
    info = check(force=True)
    if info.get("yeni_var") and last != info["uzak"]:
        STATE["_bildirildi"] = info["uzak"]
        notify(f"Yeni JARVIS sürümü hazır: v{info['uzak']}. Ayarlar > GÜNCELLE'ye bas. " + " · ".join(info.get("notlar", [])[:3]), "info")
