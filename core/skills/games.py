"""Oyun: Steam/Epic kütüphanesi, oyun başlatma/kapatma, FPS ölçümü (PresentMon), oyun performans oturumu."""
import csv
import glob
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from ..config import ROOT
from ..tools import N, S, _schema

IS_WIN = sys.platform.startswith("win")

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None


# ===================== kütüphane =====================
def _steam_root():
    if IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                return Path(winreg.QueryValueEx(k, "SteamPath")[0])
        except Exception:
            p = Path("C:/Program Files (x86)/Steam")
            return p if p.exists() else None
    p = Path.home() / ".steam/steam"
    return p if p.exists() else None


def _vdf_paths(text):
    return [m.replace("\\\\", "\\") for m in re.findall(r'"path"\s+"([^"]+)"', text)]


def parse_acf(text):
    name = re.search(r'"name"\s+"([^"]+)"', text)
    appid = re.search(r'"appid"\s+"(\d+)"', text)
    folder = re.search(r'"installdir"\s+"([^"]+)"', text)
    size = re.search(r'"SizeOnDisk"\s+"(\d+)"', text)
    return {"ad": name.group(1) if name else "?", "id": appid.group(1) if appid else "",
            "klasör": folder.group(1) if folder else "", "boyut_gb": round(int(size.group(1)) / 1e9, 1) if size else None}


def game_library():
    games = []
    root = _steam_root()
    if root:
        libs = [root]
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            libs += [Path(p) for p in _vdf_paths(vdf.read_text(encoding="utf-8", errors="ignore"))]
        seen = set()
        for lib in libs:
            for acf in glob.glob(str(lib / "steamapps" / "appmanifest_*.acf")):
                g = parse_acf(Path(acf).read_text(encoding="utf-8", errors="ignore"))
                if g["id"] in seen or g["id"] in ("228980",):  # Steamworks redist
                    continue
                seen.add(g["id"])
                g["platform"] = "Steam"
                g["yol"] = str(lib / "steamapps" / "common" / g["klasör"])
                games.append(g)
    epic = Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
    if epic.exists():
        for item in epic.glob("*.item"):
            try:
                d = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
                games.append({"ad": d.get("DisplayName"), "id": d.get("AppName"), "platform": "Epic",
                              "yol": d.get("InstallLocation"), "exe": d.get("LaunchExecutable"),
                              "boyut_gb": round(d.get("InstallSize", 0) / 1e9, 1)})
            except Exception:
                pass
    return sorted(games, key=lambda g: (g["ad"] or "").lower()) or "Steam veya Epic'te kurulu oyun bulunamadı."


def _find_game(name):
    lib = game_library()
    if isinstance(lib, str):
        raise RuntimeError(lib)
    n = name.lower()
    for g in lib:
        if (g["ad"] or "").lower() == n:
            return g
    for g in lib:
        if n in (g["ad"] or "").lower():
            return g
    raise RuntimeError(f"'{name}' kütüphanede bulunamadı.")


def _open(uri):
    if IS_WIN:
        os.startfile(uri)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", uri])


def game_launch(name):
    g = _find_game(name)
    if g["platform"] == "Steam":
        _open(f"steam://rungameid/{g['id']}")
    else:
        _open(f"com.epicgames.launcher://apps/{g['id']}?action=launch&silent=true")
    return f"Başlatılıyor: {g['ad']} ({g['platform']}). İyi oyunlar!"


def game_close(name):
    g = _find_game(name)
    if not psutil:
        return "psutil yok"
    base = os.path.normcase(g.get("yol") or "")
    killed = 0
    for p in psutil.process_iter(["exe"]):
        try:
            if base and p.info["exe"] and os.path.normcase(p.info["exe"]).startswith(base):
                p.terminate()
                killed += 1
        except Exception:
            pass
    return f"{g['ad']} kapatıldı." if killed else f"{g['ad']} çalışmıyor görünüyor."


def _running_game():
    lib = game_library()
    if isinstance(lib, str) or not psutil:
        return None, None
    paths = {os.path.normcase(g["yol"]): g for g in lib if g.get("yol")}
    best = None
    for p in psutil.process_iter(["exe", "name", "memory_info"]):
        try:
            exe = os.path.normcase(p.info["exe"] or "")
            for base, g in paths.items():
                if exe.startswith(base):
                    mem = p.info["memory_info"].rss if p.info["memory_info"] else 0
                    if not best or mem > best[2]:
                        best = (g, p.info["name"], mem)
        except Exception:
            pass
    return (best[0], best[1]) if best else (None, None)


# ===================== FPS (PresentMon) =====================
def _presentmon():
    for c in [*glob.glob(str(ROOT / "tools" / "PresentMon*.exe")), shutil.which("PresentMon"), shutil.which("PresentMon.exe")]:
        if c and os.path.exists(c):
            return c
    return None


def parse_presentmon(csv_text):
    rows = list(csv.DictReader(csv_text.splitlines()))
    if not rows:
        return None
    col = next((c for c in ("MsBetweenPresents", "msBetweenPresents", "FrameTime", "MsBetweenDisplayChange") if c in rows[0]), None)
    if not col:
        return None
    ft = [float(r[col]) for r in rows if r.get(col) not in (None, "", "NA") and float(r[col]) > 0]
    if len(ft) < 5:
        return None
    ft_sorted = sorted(ft)
    p99 = ft_sorted[int(len(ft) * 0.99) - 1]
    return {"ortalama_fps": round(1000 / statistics.mean(ft), 1), "%1_düşük_fps": round(1000 / p99, 1),
            "en_düşük_fps": round(1000 / max(ft), 1), "ortalama_kare_süresi_ms": round(statistics.mean(ft), 2), "kare": len(ft)}


def game_fps(seconds=10, process=""):
    pm = _presentmon()
    if not pm:
        return ("FPS ölçmek için Intel PresentMon gerekli (ücretsiz): github.com/GameTechDev/PresentMon/releases → "
                "PresentMon-x.x.x-x64.exe dosyasını JARVIS klasöründeki 'tools' klasörüne koy.")
    if not process:
        _, process = _running_game()
    if not process:
        return "Çalışan bir oyun bulunamadı; process adını ver (örn. cs2.exe)."
    out = Path(tempfile.gettempdir()) / f"jarvis_pm_{int(time.time())}.csv"
    subprocess.run([pm, "--process_name", process, "--output_file", str(out), "--timed", str(int(seconds)),
                    "--terminate_after_timed", "--stop_existing_session"], capture_output=True, timeout=int(seconds) + 30,
                   creationflags=0x08000000 if IS_WIN else 0)
    if not out.exists():
        return "PresentMon veri üretmedi (yönetici olarak çalıştırmak gerekebilir)."
    res = parse_presentmon(out.read_text(errors="ignore"))
    out.unlink(missing_ok=True)
    return {"oyun": process, **res} if res else "Yeterli kare verisi yok."


# ===================== performans oturumu =====================
_session = {"thread": None, "stop": False, "samples": [], "game": None, "start": 0}


def _gpu_now():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4)
        if r.returncode == 0:
            u, t, m = [float(x) for x in r.stdout.splitlines()[0].split(",")]
            return u, t, m
    except Exception:
        pass
    return None, None, None


def _sampler():
    while not _session["stop"]:
        u, t, m = _gpu_now()
        _session["samples"].append({"cpu": psutil.cpu_percent(interval=None) if psutil else None,
                                    "ram": psutil.virtual_memory().percent if psutil else None,
                                    "gpu": u, "gpu_c": t, "vram": m})
        time.sleep(2)


def game_session(action="start"):
    """Oyun oynarken CPU/RAM/GPU'yu kaydeder; stop ile rapor verir."""
    if action == "start":
        if _session["thread"] and _session["thread"].is_alive():
            return "Zaten kayıt yapılıyor."
        g, proc = _running_game()
        _session.update(stop=False, samples=[], game=(g or {}).get("ad"), proc=proc, start=time.time())
        _session["thread"] = threading.Thread(target=_sampler, daemon=True)
        _session["thread"].start()
        return f"Performans kaydı başladı{(' (' + _session['game'] + ')') if _session['game'] else ''}. Bitince 'oyun oturumunu bitir' de."
    _session["stop"] = True
    s = _session["samples"]
    if not s:
        return "Kayıt yok."

    def agg(k):
        v = [x[k] for x in s if x[k] is not None]
        return {"ort": round(statistics.mean(v), 1), "max": round(max(v), 1)} if v else "ölçülemedi"
    rep = {"oyun": _session["game"], "süre_dk": round((time.time() - _session["start"]) / 60, 1),
           "cpu_%": agg("cpu"), "ram_%": agg("ram"), "gpu_%": agg("gpu"), "gpu_sıcaklık_c": agg("gpu_c")}
    tips = []
    if isinstance(rep["cpu_%"], dict) and rep["cpu_%"]["ort"] > 85:
        tips.append("İşlemci darboğazı: arka plandaki programları kapat, grafik ayarlarında CPU yükünü (kalabalık, gölge mesafesi) düşür.")
    if isinstance(rep["gpu_%"], dict) and rep["gpu_%"]["ort"] > 95:
        tips.append("Ekran kartı tam yükte: çözünürlük/ölçekleme (DLSS/FSR) veya grafik kalitesini düşür.")
    if isinstance(rep["gpu_sıcaklık_c"], dict) and rep["gpu_sıcaklık_c"]["max"] > 83:
        tips.append("GPU sıcak: fanları ve havalandırmayı kontrol et.")
    if isinstance(rep["ram_%"], dict) and rep["ram_%"]["max"] > 90:
        tips.append("RAM dolu: tarayıcı sekmelerini kapat.")
    rep["öneriler"] = tips or ["Sistem rahat görünüyor."]
    return rep


# ---------------- OBS Studio (yayın ve kayıt) ----------------

def _obs_session():
    """OBS WebSocket v5 (OBS 28+ içinde gömülü): Araçlar > WebSocket Sunucu Ayarları > Etkinleştir. Parola .env OBS_PASSWORD."""
    import base64
    import hashlib
    from ..config import env
    from .worldwatch import _WS
    host, port = (env("OBS_HOST") or "127.0.0.1"), int(env("OBS_PORT") or 4455)
    try:
        ws = _WS(host, "/", port=port, tls=False, timeout=5)
    except Exception as e:
        raise RuntimeError(f"OBS'e bağlanılamadı ({host}:{port}). OBS açık mı ve Araçlar > WebSocket Sunucu Ayarları > 'WebSocket sunucusunu etkinleştir' işaretli mi? ({e})")
    hello = json.loads(ws.recv())
    ident = {"rpcVersion": 1}
    auth = hello.get("d", {}).get("authentication")
    if auth:
        pw = env("OBS_PASSWORD")
        if not pw:
            ws.close()
            raise RuntimeError("OBS parola istiyor: .env dosyasına OBS_PASSWORD ekle (OBS > WebSocket Sunucu Ayarları > Bağlantı Bilgilerini Göster).")
        secret = base64.b64encode(hashlib.sha256((pw + auth["salt"]).encode()).digest()).decode()
        ident["authentication"] = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
    ws.send(json.dumps({"op": 1, "d": ident}))
    r = json.loads(ws.recv())
    if r.get("op") != 2:
        ws.close()
        raise RuntimeError("OBS kimlik doğrulaması başarısız (parola yanlış olabilir).")
    return ws


def _obs_req(ws, rtype, data=None):
    rid = str(time.time())
    ws.send(json.dumps({"op": 6, "d": {"requestType": rtype, "requestId": rid, "requestData": data or {}}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("op") == 7 and m["d"].get("requestId") == rid:
            st = m["d"].get("requestStatus", {})
            if not st.get("result"):
                raise RuntimeError(f"OBS: {st.get('comment') or st.get('code')}")
            return m["d"].get("responseData") or {}


def obs_control(action, value=""):
    """OBS: record_start/record_stop/record_pause/record_resume, stream_start/stream_stop, replay_save (anı kaydet), scene (value=sahne adı),
    scenes (liste), mute/unmute (value=kaynak adı), status."""
    a = (action or "").lower()
    ws = _obs_session()
    try:
        if a in ("status", "durum"):
            rec, st, sc = _obs_req(ws, "GetRecordStatus"), _obs_req(ws, "GetStreamStatus"), _obs_req(ws, "GetCurrentProgramScene")
            return {"kayıt": "açık" if rec.get("outputActive") else "kapalı", "kayıt_süresi": rec.get("outputTimecode"), "yayın": "açık" if st.get("outputActive") else "kapalı",
                    "yayın_süresi": st.get("outputTimecode"), "sahne": sc.get("currentProgramSceneName") or sc.get("sceneName")}
        if a in ("scenes", "sahneler"):
            return [x["sceneName"] for x in _obs_req(ws, "GetSceneList").get("scenes", [])][::-1]
        if a in ("scene", "sahne"):
            _obs_req(ws, "SetCurrentProgramScene", {"sceneName": value})
            return f"Sahne değişti: {value}"
        if a in ("mute", "unmute", "sustur"):
            _obs_req(ws, "SetInputMute", {"inputName": value, "inputMuted": a != "unmute"})
            return f"{value}: {'sessiz' if a != 'unmute' else 'açık'}"
        req = {"record_start": "StartRecord", "record_stop": "StopRecord", "record_pause": "PauseRecord", "record_resume": "ResumeRecord",
               "stream_start": "StartStream", "stream_stop": "StopStream", "replay_save": "SaveReplayBuffer", "replay_start": "StartReplayBuffer"}.get(a)
        if not req:
            return "İşlemler: status, scenes, scene, record_start/stop/pause/resume, stream_start/stop, replay_start, replay_save, mute/unmute"
        r = _obs_req(ws, req)
        return {"tamam": req, **({"dosya": r["outputPath"]} if r.get("outputPath") else {})}
    finally:
        ws.close()


TOOLS = {
    "obs_control": (obs_control, _schema("OBS Studio'yu yönetir: kayıt başlat/durdur, yayın başlat/durdur, sahne değiştir, anı kaydet (replay), mikrofon sustur, durum.",
                                         {"action": S("record_start/record_stop/stream_start/stream_stop/scene/scenes/replay_save/mute/unmute/status"), "value": S("sahne/kaynak adı")}, ["action"]),
                    lambda a: str(a.get("action", "")).startswith("stream_start")),
    "game_library": (game_library, _schema("Kurulu Steam ve Epic oyunları."), False),
    "game_launch": (game_launch, _schema("Oyunu başlatır.", {"name": S("oyun adı")}, ["name"]), False),
    "game_close": (game_close, _schema("Çalışan oyunu kapatır.", {"name": S("oyun adı")}, ["name"]), True),
    "game_fps": (game_fps, _schema("Çalışan oyunun FPS'ini ölçer (ortalama, %1 düşük).",
                                   {"seconds": N("kaç saniye"), "process": S("oyun exe adı (boşsa otomatik)")}), False),
    "game_session": (game_session, _schema("Oyun sırasında performans kaydı başlatır/bitirir ve öneri verir.",
                                           {"action": {"type": "string", "enum": ["start", "stop"]}}), False),
}
