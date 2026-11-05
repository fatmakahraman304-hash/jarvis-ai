"""Kontrol merkezi: acil durdurma, misafir modu, güvenli mod (internet kesilince), geri alma, program kurma/kaldırma (winget),
çoklu monitör, Windows ayarları, gizlilik denetimi, yetkisiz erişim uyarıları, ağ araçları, robot kol, el hareketi fare komutları."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from .. import memory
from ..config import DATA, load_settings, save_settings
from ..tools import N, S, _path, _schema

IS_WIN = sys.platform.startswith("win")
ESTOP = threading.Event()
STATE = {"online": True, "safe_mode": False, "known_usb": None, "known_ports": None}

memory.ensure("""
CREATE TABLE IF NOT EXISTS undo_log(id INTEGER PRIMARY KEY AUTOINCREMENT, op TEXT, data TEXT, ts REAL, undone INTEGER DEFAULT 0);
""")


def _ps(cmd, timeout=60):
    if not IS_WIN:
        raise RuntimeError("Bu özellik Windows'ta çalışır.")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout, creationflags=0x08000000)
    return (r.stdout or r.stderr or "").strip()


# ===================== ACİL DURDURMA =====================
def emergency_stop(reason="kullanıcı"):
    ESTOP.set()
    from .. import brain
    n_pending = len(brain.pending_list())
    for p in brain.pending_list():
        brain._pending.pop(p["id"], None)
    memory._q("UPDATE tasks SET enabled=0 WHERE enabled=1", commit=True)
    save_settings({"auto_control": False})
    memory.notify(f"⛔ ACİL DURDURMA ({reason}): tüm otomatik görevler durduruldu, {n_pending} bekleyen işlem iptal edildi, otonom ekran kontrolü kapatıldı.", "error")
    memory.log_action("emergency_stop", {"reason": reason}, "ok", True)
    return "Acil durdurma yapıldı. Devam etmek için 'acil durumu kaldır' de (görevler durdurulmuş olarak kalır, istediklerini tek tek aç)."


def emergency_reset():
    ESTOP.clear()
    return "Acil durum kaldırıldı. Görevler hâlâ durdurulmuş; task_control ile istediğini devam ettirebilirsin."


# ===================== GERİ ALMA =====================
def journal(op, **data):
    memory._q("INSERT INTO undo_log(op, data, ts) VALUES(?,?,?)", (op, json.dumps(data, ensure_ascii=False), time.time()), commit=True)


def undo_last(count=1):
    rows = memory._q("SELECT * FROM undo_log WHERE undone=0 ORDER BY id DESC LIMIT ?", (int(count),))
    if not rows:
        return "Geri alınacak işlem yok."
    out = []
    for r in rows:
        d = json.loads(r["data"])
        try:
            if r["op"] == "move":
                shutil.move(d["dst"], d["src"])
                out.append(f"geri taşındı: {d['src']}")
            elif r["op"] == "delete":
                os.makedirs(os.path.dirname(d["src"]), exist_ok=True)
                shutil.move(d["trash"], d["src"])
                out.append(f"geri getirildi: {d['src']}")
            elif r["op"] == "write":
                if d.get("backup"):
                    shutil.copyfile(d["backup"], d["path"])
                    out.append(f"önceki içerik geri yüklendi: {d['path']}")
                else:
                    os.remove(d["path"])
                    out.append(f"oluşturulan dosya kaldırıldı: {d['path']}")
            elif r["op"] == "organize":
                for src, dst in reversed(d["moves"]):
                    if os.path.exists(dst):
                        shutil.move(dst, src)
                out.append(f"klasör düzeni geri alındı ({len(d['moves'])} dosya)")
            memory._q("UPDATE undo_log SET undone=1 WHERE id=?", (r["id"],), commit=True)
        except Exception as e:
            out.append(f"{r['op']} geri alınamadı: {e}")
    return out


def undo_history(limit=15):
    rows = memory._q("SELECT id, op, data, ts, undone FROM undo_log ORDER BY id DESC LIMIT ?", (int(limit),))
    return [{"no": r["id"], "işlem": r["op"], "zaman": time.strftime("%d.%m %H:%M", time.localtime(r["ts"])),
             "geri_alındı": bool(r["undone"]), "ayrıntı": r["data"][:150]} for r in rows] or "Kayıt yok."


def empty_trash(days=30):
    trash = DATA / "cop_kutusu"
    if not trash.exists():
        return "Çöp kutusu boş."
    n, cut = 0, time.time() - float(days) * 86400
    for f in trash.iterdir():
        if f.stat().st_mtime < cut:
            (shutil.rmtree if f.is_dir() else os.remove)(f)
            n += 1
    return f"{n} öğe kalıcı olarak silindi ({days} günden eski)."


# ===================== PROGRAM KUR / KALDIR =====================
def _winget(args, timeout=900):
    if not IS_WIN:
        raise RuntimeError("winget Windows'ta çalışır.")
    r = subprocess.run(["winget", *args, "--accept-source-agreements", "--disable-interactivity"], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=timeout, creationflags=0x08000000)
    out = re.sub(r"[\r\x08]+", "\n", r.stdout or r.stderr or "")
    lines = [ln for ln in out.splitlines() if ln.strip() and not re.match(r"^[\s\-\\|/█▒]+$", ln)]
    return "\n".join(lines[-40:])


def app_search(query):
    return _winget(["search", query, "--count", "12"], 120)


def app_install(app_id):
    return _winget(["install", "--id", app_id, "-e", "--accept-package-agreements", "--silent"])


def app_uninstall(name):
    return _winget(["uninstall", name, "--silent"])


def app_upgrades(apply=False):
    if str(apply).lower() in ("true", "1"):
        return _winget(["upgrade", "--all", "--accept-package-agreements", "--silent"], 3600)
    return _winget(["upgrade"], 120)


# ===================== MONİTÖRLER / AYARLAR =====================
def monitors():
    if not IS_WIN:
        return "Windows'ta çalışır."
    import ctypes
    from ctypes import wintypes
    out = []

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    CB = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(h, hdc, rc, lp):
        mi = MI(); mi.cbSize = ctypes.sizeof(MI)
        ctypes.windll.user32.GetMonitorInfoW(h, ctypes.byref(mi))
        r = mi.rcMonitor
        out.append({"no": len(out) + 1, "x": r.left, "y": r.top, "genişlik": r.right - r.left, "yükseklik": r.bottom - r.top, "ana": bool(mi.dwFlags & 1)})
        return 1
    ctypes.windll.user32.EnumDisplayMonitors(None, None, CB(cb), 0)
    return out


def move_window_to_monitor(title, monitor=2, maximize=True):
    from .computer import _windows
    import ctypes
    mons = monitors()
    if int(monitor) > len(mons):
        return f"Sadece {len(mons)} monitör var."
    m = mons[int(monitor) - 1]
    wins = [w for w in _windows() if title.lower() in w[1].lower()]
    if not wins:
        return f"'{title}' penceresi yok."
    h = wins[0][0]
    u = ctypes.windll.user32
    u.ShowWindow(h, 9)
    u.MoveWindow(h, m["x"] + 40, m["y"] + 40, int(m["genişlik"] * 0.8), int(m["yükseklik"] * 0.8), True)
    if str(maximize).lower() in ("true", "1"):
        u.ShowWindow(h, 3)
    return f"'{wins[0][1]}' {monitor}. monitöre taşındı."


def arrange_windows(layout="side_by_side", titles=""):
    """İki pencereyi yan yana / üst üste dizer ya da tüm pencereleri ızgaraya dizer."""
    from .computer import _windows
    import ctypes
    u = ctypes.windll.user32
    mons = monitors()
    m = next((x for x in mons if x["ana"]), mons[0])
    ws = _windows()
    if titles:
        want = [t.strip().lower() for t in titles.split(",")]
        ws = [w for t in want for w in ws if t in w[1].lower()][: len(want)]
    else:
        ws = [w for w in ws if w[1] not in ("JARVIS",)][:4]
    if not ws:
        return "Dizilecek pencere yok."
    n = len(ws)
    for i, (h, name) in enumerate(ws):
        u.ShowWindow(h, 9)
        if layout == "stack":
            u.MoveWindow(h, m["x"], m["y"] + i * m["yükseklik"] // n, m["genişlik"], m["yükseklik"] // n, True)
        elif layout == "grid" and n > 2:
            cols = 2
            rows = (n + 1) // 2
            u.MoveWindow(h, m["x"] + (i % cols) * m["genişlik"] // cols, m["y"] + (i // cols) * m["yükseklik"] // rows, m["genişlik"] // cols, m["yükseklik"] // rows, True)
        else:
            u.MoveWindow(h, m["x"] + i * m["genişlik"] // n, m["y"], m["genişlik"] // n, m["yükseklik"], True)
    return f"{n} pencere düzenlendi ({layout})."


def virtual_desktop(action="new"):
    from .computer import key_press
    keys = {"new": "win+ctrl+d", "next": "win+ctrl+right", "prev": "win+ctrl+left", "close": "win+ctrl+f4", "overview": "win+tab"}
    if action not in keys:
        return "Geçerli: new, next, prev, close, overview"
    key_press(keys[action])
    return f"Sanal masaüstü: {action}"


def windows_setting(name, value=""):
    n = name.lower()
    if n in ("dark_mode", "karanlık", "koyu"):
        v = 0 if str(value).lower() in ("on", "aç", "true", "1", "") else 1
        _ps(f"Set-ItemProperty HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize -Name AppsUseLightTheme -Value {v}; "
            f"Set-ItemProperty HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize -Name SystemUsesLightTheme -Value {v}")
        return f"Koyu tema {'açıldı' if v == 0 else 'kapatıldı'}."
    if n in ("wallpaper", "duvar kağıdı"):
        import ctypes
        p = str(_path(value))
        if not os.path.exists(p):
            return "Resim bulunamadı."
        ctypes.windll.user32.SystemParametersInfoW(20, 0, p, 3)
        return "Duvar kağıdı değiştirildi."
    if n in ("power_plan", "güç"):
        plans = {"yüksek": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "high": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
                 "dengeli": "381b4222-f694-41f0-9685-ff5bb260df2e", "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
                 "tasarruf": "a1841308-3541-4fab-bc81-f71556f20b4a", "saver": "a1841308-3541-4fab-bc81-f71556f20b4a"}
        g = plans.get(str(value).lower())
        if not g:
            return "Geçerli: yüksek, dengeli, tasarruf"
        _ps(f"powercfg /setactive {g}")
        return f"Güç planı: {value}"
    if n in ("night_light", "gece ışığı", "settings", "ayarlar"):
        page = {"night_light": "ms-settings:nightlight", "gece ışığı": "ms-settings:nightlight"}.get(n, f"ms-settings:{value}" if value else "ms-settings:")
        os.startfile(page)  # type: ignore[attr-defined]
        return f"Ayar sayfası açıldı: {page}"
    return "Desteklenen: dark_mode, wallpaper, power_plan, night_light, settings (sayfa adı)"


# ===================== GİZLİLİK / GÜVENLİK İZLEME =====================
def privacy_audit():
    if not IS_WIN:
        return "Windows'ta çalışır."
    script = r"""
$res=@()
foreach($cap in 'webcam','microphone','location'){
 foreach($root in "HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\$cap","HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\$cap\NonPackaged"){
  if(Test-Path $root){ Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
   $p=Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
   if($p.LastUsedTimeStart){ $res += [pscustomobject]@{cihaz=$cap; uygulama=($_.PSChildName -replace '#','\'); izin=$p.Value; son=[DateTime]::FromFileTime($p.LastUsedTimeStart).ToString('dd.MM HH:mm'); suanda=($p.LastUsedTimeStop -eq 0)} }
  }}}}
$res | Sort-Object son -Descending | Select-Object -First 25 | ConvertTo-Json -Compress
"""
    out = _ps(script)
    try:
        v = json.loads(out) if out else []
        v = v if isinstance(v, list) else [v]
        live = [x for x in v if x.get("suanda")]
        return {"şu_anda_kullanan": live or "yok", "son_kullananlar": v}
    except Exception:
        return out[:1500]


def security_watch_tick(notify):
    """Yeni USB cihazı, yeni dışa açık port ve (yönetici izniyle) başarısız oturum açma denemelerini bildirir."""
    try:
        import psutil
        ports = {f"{(psutil.Process(c.pid).name() if c.pid else '?')}:{c.laddr.port}" for c in psutil.net_connections("inet")
                 if c.status == "LISTEN" and c.laddr.ip in ("0.0.0.0", "::")}
        if STATE["known_ports"] is not None:
            for p in ports - STATE["known_ports"]:
                notify(f"Güvenlik: yeni dışa açık port {p}", "error")
        STATE["known_ports"] = ports
    except Exception:
        pass
    if IS_WIN:
        try:
            usb = set(_ps("Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'} | ForEach-Object { $_.FriendlyName }").splitlines())
            if STATE["known_usb"] is not None:
                for d in usb - STATE["known_usb"]:
                    if d.strip():
                        notify(f"Yeni USB cihazı takıldı: {d.strip()}", "info")
            STATE["known_usb"] = usb
        except Exception:
            pass
        try:
            fails = _ps("(Get-WinEvent -FilterHashtable @{LogName='Security';Id=4625;StartTime=(Get-Date).AddMinutes(-5)} -ErrorAction SilentlyContinue | Measure-Object).Count")
            if fails.isdigit() and int(fails) >= 3:
                notify(f"Güvenlik uyarısı: son 5 dakikada {fails} başarısız oturum açma denemesi!", "error")
        except Exception:
            pass


def online():
    for host in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        try:
            with socket.create_connection(host, timeout=2):
                return True
        except OSError:
            continue
    return False


def connectivity_tick(notify):
    up = online()
    if up != STATE["online"]:
        STATE["online"] = up
        if not up:
            STATE["safe_mode"] = True
            notify("İnternet kesildi: güvenli moda geçildi. Otomatik görevler bekletiliyor, yerel model (Ollama) varsa o kullanılır.", "error")
        else:
            STATE["safe_mode"] = False
            notify("İnternet geri geldi: güvenli mod kapandı, görevler devam ediyor.", "info")


# ===================== AĞ =====================
def lan_devices():
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
    devs = []
    for ln in out.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})\s*(\w*)", ln)
        if m and not m.group(1).endswith(".255") and not m.group(1).startswith(("224.", "239.")):
            ip, mac = m.group(1), m.group(2).lower().replace(":", "-")
            try:
                name = socket.gethostbyaddr(ip)[0]
            except Exception:
                name = ""
            devs.append({"ip": ip, "mac": mac, "ad": name})
    return devs or "Cihaz bulunamadı (arp tablosu boş)."


def ping_test(host="8.8.8.8", count=10):
    flag = "-n" if IS_WIN else "-c"
    r = subprocess.run(["ping", flag, str(int(count)), host], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=60)
    times = [float(x.replace(",", ".")) for x in re.findall(r"[=<]\s?(\d+[.,]?\d*)\s?ms", r.stdout)]
    sent = int(count)
    return {"hedef": host, "gönderilen": sent, "alınan": len(times), "kayıp_%": round(100 * (sent - len(times)) / sent),
            "ort_ms": round(sum(times) / len(times), 1) if times else None, "min_ms": min(times) if times else None,
            "maks_ms": max(times) if times else None, "dalgalanma_ms": round(max(times) - min(times), 1) if times else None}


def speed_test(mb=25):
    url = f"https://speed.cloudflare.com/__down?bytes={int(mb) * 1_000_000}"
    t0 = time.time()
    total = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "JARVIS"}), timeout=60) as r:
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            total += len(b)
    down = total * 8 / (time.time() - t0) / 1e6
    data = os.urandom(5_000_000)
    t0 = time.time()
    try:
        urllib.request.urlopen(urllib.request.Request("https://speed.cloudflare.com/__up", data=data, headers={"User-Agent": "JARVIS", "Content-Type": "application/octet-stream"}), timeout=60).read()
        up = len(data) * 8 / (time.time() - t0) / 1e6
    except Exception:
        up = None
    p = ping_test("1.1.1.1", 5)
    return {"indirme_mbps": round(down, 1), "yükleme_mbps": round(up, 1) if up else "ölçülemedi", "ping_ms": p["ort_ms"], "kayıp_%": p["kayıp_%"]}


def network_diagnose():
    rep = {"internet": online()}
    try:
        gw = re.search(r"Default Gateway[ .:]*([\d.]+)|Varsayılan Ağ Geçidi[ .:]*([\d.]+)", subprocess.run(["ipconfig"], capture_output=True, text=True, errors="ignore").stdout) if IS_WIN else None
        g = (gw.group(1) or gw.group(2)) if gw else None
    except Exception:
        g = None
    if g:
        rep["modem"] = ping_test(g, 4)
    rep["internet_ping"] = ping_test("1.1.1.1", 4)
    try:
        socket.gethostbyname("google.com")
        rep["dns"] = "çalışıyor"
    except Exception:
        rep["dns"] = "ÇALIŞMIYOR"
    tips = []
    if g and rep["modem"]["kayıp_%"] > 0:
        tips.append("Modeme bile paket kaybı var: Wi-Fi sinyali zayıf ya da kablo sorunu. Modeme yaklaş veya kablo kullan.")
    if rep["internet_ping"]["kayıp_%"] > 0 and not (g and rep["modem"]["kayıp_%"] > 0):
        tips.append("Modem iyi ama internette kayıp var: sorun büyük olasılıkla internet sağlayıcısında. Modemi yeniden başlatmayı dene.")
    if rep["dns"] != "çalışıyor":
        tips.append("DNS çalışmıyor: DNS'i 1.1.1.1 veya 8.8.8.8 yapmayı dene.")
    rep["öneriler"] = tips or ["Ağ sağlıklı görünüyor."]
    return rep


# ===================== ROBOT KOL =====================
_serial = {"conn": None, "port": None}


def _serial_conn(port, baud):
    import serial  # type: ignore
    if _serial["conn"] is None or _serial["port"] != port:
        if _serial["conn"]:
            _serial["conn"].close()
        _serial["conn"] = serial.Serial(port, int(baud), timeout=1)
        _serial["port"] = port
        time.sleep(1.8)
    return _serial["conn"]


def robot_arm(base=90, shoulder=90, elbow=90, gripper=90, wrist=90):
    """Açılar 0-180. Komut: 'S{taban},{omuz},{dirsek},{bilek},{kıskaç}\\n' (arduino/jarvis_robot_arm.ino ile uyumlu)."""
    vals = [max(0, min(180, int(float(v)))) for v in (base, shoulder, elbow, wrist, gripper)]
    cmd = "S" + ",".join(map(str, vals)) + "\n"
    s = load_settings()
    if s.get("robot_url"):
        urllib.request.urlopen(urllib.request.Request(s["robot_url"].rstrip("/") + "/arm", data=json.dumps(dict(zip(["base", "shoulder", "elbow", "wrist", "gripper"], vals))).encode(),
                                                      headers={"Content-Type": "application/json"}), timeout=2).read()
        return f"Robot (ağ): {vals}"
    port = s.get("robot_port")
    if not port:
        return "Robot bağlı değil: Ayarlar'da robot_port (ör. COM3) veya robot_url (ESP32 adresi) belirle."
    _serial_conn(port, s.get("robot_baud", 115200)).write(cmd.encode())
    return f"Robot: taban {vals[0]}°, omuz {vals[1]}°, dirsek {vals[2]}°, bilek {vals[3]}°, kıskaç {vals[4]}°"


def robot_config(port="", url="", baud=115200):
    save_settings({"robot_port": port, "robot_url": url, "robot_baud": int(baud)})
    return f"Robot ayarı kaydedildi: {port or url}"


def serial_read(port, seconds=3, baud=9600):
    import serial  # type: ignore
    with serial.Serial(port, int(baud), timeout=0.5) as s:
        t0, out = time.time(), b""
        while time.time() - t0 < float(seconds):
            out += s.read(256)
    return out.decode("utf-8", "ignore")[-3000:] or "(veri yok)"


# ===================== el hareketlerinden gelen fare/klavye (sunucu uç noktası kullanır) =====================
def gesture_mouse(action, x=None, y=None, amount=0):
    import ctypes
    u = ctypes.windll.user32
    if x is not None and y is not None:
        vx, vy, vw, vh = u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        u.SetCursorPos(int(vx + float(x) * vw), int(vy + float(y) * vh))
    flags = {"down": 0x2, "up": 0x4, "right": None}
    if action == "down":
        u.mouse_event(0x2, 0, 0, 0, 0)
    elif action == "up":
        u.mouse_event(0x4, 0, 0, 0, 0)
    elif action == "right":
        u.mouse_event(0x8, 0, 0, 0, 0); u.mouse_event(0x10, 0, 0, 0, 0)
    elif action == "scroll":
        u.mouse_event(0x800, 0, 0, int(amount) * 120, 0)
    return "ok"


def brightness_delta(delta):
    cur = _ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness")
    v = max(0, min(100, (int(cur) if cur.strip().isdigit() else 50) + int(delta)))
    _ps(f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{v})")
    return v


TOOLS = {
    "emergency_stop": (emergency_stop, _schema("ACİL DURDURMA: tüm otomatik görevleri, bekleyen işlemleri ve otonom ekran kontrolünü anında durdurur.", {"reason": S("neden")}), False),
    "emergency_reset": (emergency_reset, _schema("Acil durumu kaldırır."), False),
    "undo_last": (undo_last, _schema("Son dosya işlemlerini GERİ ALIR (taşıma, silme, üzerine yazma, klasör düzenleme).", {"count": N("kaç işlem")}), False),
    "undo_history": (undo_history, _schema("Geri alınabilir işlem geçmişi."), False),
    "empty_trash": (empty_trash, _schema("JARVIS çöp kutusundaki eski dosyaları kalıcı siler.", {"days": N("kaç günden eski")}), True),
    "app_search": (app_search, _schema("Kurulabilecek programları arar (winget).", {"query": S("program")}, ["query"]), False),
    "app_install": (app_install, _schema("Program kurar (winget id ile; önce app_search ile id bul).", {"app_id": S("örn. VideoLAN.VLC")}, ["app_id"]), True),
    "app_uninstall": (app_uninstall, _schema("Program kaldırır.", {"name": S("program adı veya id")}, ["name"]), True),
    "app_upgrades": (app_upgrades, _schema("Güncellenebilir programları listeler; apply=true ise hepsini günceller.", {"apply": {"type": "boolean"}}),
                     lambda a: str(a.get("apply")).lower() in ("true", "1")),
    "monitors": (monitors, _schema("Bağlı monitörler ve çözünürlükleri."), False),
    "move_window_to_monitor": (move_window_to_monitor, _schema("Pencereyi başka monitöre taşır.", {"title": S("pencere"), "monitor": N("monitör no"), "maximize": {"type": "boolean"}}, ["title"]), False),
    "arrange_windows": (arrange_windows, _schema("Pencereleri otomatik düzenler: side_by_side, stack, grid.", {"layout": S("düzen"), "titles": S("pencereler, virgülle (boş: açık olanlar)")}), False),
    "virtual_desktop": (virtual_desktop, _schema("Sanal masaüstü: new, next, prev, close, overview.", {"action": S("eylem")}), False),
    "windows_setting": (windows_setting, _schema("Windows ayarı: dark_mode (on/off), wallpaper (resim yolu), power_plan (yüksek/dengeli/tasarruf), night_light, settings (sayfa).",
                                                 {"name": S("ayar"), "value": S("değer")}, ["name"]), lambda a: a.get("name") in ("power_plan", "güç")),
    "privacy_audit": (privacy_audit, _schema("Kamera, mikrofon ve konumu hangi uygulamaların kullandığını (şu anda dahil) gösterir."), False),
    "lan_devices": (lan_devices, _schema("Ev ağına bağlı cihazlar (IP, MAC, ad)."), False),
    "ping_test": (ping_test, _schema("Gecikme ve paket kaybı ölçer.", {"host": S("hedef"), "count": N("kaç ping")}), False),
    "speed_test": (speed_test, _schema("İnternet hız testi (indirme, yükleme, ping)."), False),
    "network_diagnose": (network_diagnose, _schema("İnternet sorununu teşhis eder (modem, DNS, sağlayıcı) ve çözüm önerir."), False),
    "robot_arm": (robot_arm, _schema("Robot kolu açılarla hareket ettirir (0-180).", {"base": N("taban"), "shoulder": N("omuz"), "elbow": N("dirsek"), "wrist": N("bilek"), "gripper": N("kıskaç: 20 kapalı, 90 açık")}), False),
    "robot_config": (robot_config, _schema("Robot kol bağlantısı: seri port (COM3) veya ESP32 adresi.", {"port": S("COM3"), "url": S("http://192.168.1.50"), "baud": N("hız")}), False),
    "serial_read": (serial_read, _schema("Arduino/sensörden gelen veriyi okur.", {"port": S("COM3"), "seconds": N("saniye"), "baud": N("hız")}, ["port"]), False),
}
