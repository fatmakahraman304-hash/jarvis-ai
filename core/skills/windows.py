"""Windows yönetimi, donanım ve güvenlik araçları (PowerShell + psutil)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from collections import defaultdict

from ..tools import N, S, _path, _schema

IS_WIN = sys.platform.startswith("win")

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None


def _safe(v):
    """PowerShell'e giden metinden tehlikeli karakterleri temizler."""
    return "".join(ch for ch in str(v) if ch not in "'\"`;$|&{}()<>\r\n")[:120]


def ps(cmd, timeout=40, as_json=False):
    if not IS_WIN:
        raise RuntimeError("Bu özellik Windows'ta çalışır.")
    if as_json:
        cmd = f"{cmd} | ConvertTo-Json -Depth 3 -Compress"
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout,
                       creationflags=0x08000000)
    out = (r.stdout or "").strip()
    if as_json:
        try:
            v = json.loads(out) if out else []
            return v if isinstance(v, list) else [v]
        except Exception:
            return out or r.stderr.strip()
    return out or r.stderr.strip() or "(çıktı yok)"


# ===================== ekran / ağ / cihazlar =====================
def brightness(level=None):
    if level is None or level == "":
        v = ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness")
        return f"Parlaklık: %{v}" if v.strip().isdigit() else "Parlaklık okunamadı (harici monitörlerde desteklenmez)."
    lvl = max(0, min(100, int(level)))
    ps(f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{lvl})")
    return f"Parlaklık %{lvl} yapıldı."


def wifi_status():
    info = ps("netsh wlan show interfaces")
    nets = ps("netsh wlan show networks mode=bssid | Select-String 'SSID|Signal|Sinyal' | Select-Object -First 30 | ForEach-Object { $_.Line.Trim() }")
    return {"bağlantı": info[:1500], "çevredeki_ağlar": nets[:1500]}


def wifi_toggle(on=True):
    name = ps("(Get-NetAdapter | Where-Object {$_.InterfaceDescription -match 'Wireless|Wi-Fi|WLAN|802.11'} | Select-Object -First 1).Name")
    if not name or "(" in name:
        return "Wi-Fi adaptörü bulunamadı."
    ps(f"{'Enable' if on else 'Disable'}-NetAdapter -Name '{name}' -Confirm:$false")
    return f"Wi-Fi {'açıldı' if on else 'kapatıldı'}."


def network_info():
    out = {"bağdaştırıcılar": ps("Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name, InterfaceDescription, LinkSpeed", as_json=True),
           "ip": ps("Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*'} | Select-Object InterfaceAlias, IPAddress", as_json=True)}
    try:
        t0 = time.time()
        subprocess.run(["ping", "-n", "1", "8.8.8.8"], capture_output=True, timeout=5)
        out["internet_ping_ms"] = int((time.time() - t0) * 1000)
    except Exception:
        out["internet_ping_ms"] = None
    return out


def bluetooth_devices():
    return ps("Get-PnpDevice -Class Bluetooth | Where-Object {$_.FriendlyName -notmatch 'Enumerator|RFCOMM|Microsoft'} | Select-Object FriendlyName, Status", as_json=True)


def bluetooth_toggle(on=True):
    script = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
        "$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods()|?{$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'})[0];"
        "Function Await($t,$r){$n=$asTask.MakeGenericMethod($r);$x=$n.Invoke($null,@($t));$x.Wait(-1)|Out-Null;$x.Result};"
        "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null;"
        "$radios=Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]);"
        "$bt=$radios|?{$_.Kind -eq 'Bluetooth'};"
        f"Await ($bt.SetStateAsync('{'On' if on else 'Off'}')) ([Windows.Devices.Radios.RadioAccessStatus])|Out-Null;'ok'"
    )
    r = ps(script)
    return f"Bluetooth {'açıldı' if on else 'kapatıldı'}." if "ok" in r else f"Bluetooth değiştirilemedi: {r[:200]}"


def printers(action="list", name=""):
    name = _safe(name)
    if action == "default" and name:
        ps(f"(Get-CimInstance Win32_Printer | Where-Object Name -like '*{name}*' | Select-Object -First 1) | Invoke-CimMethod -MethodName SetDefaultPrinter")
        return f"Varsayılan yazıcı: {name}"
    if action == "queue":
        return ps("Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | Select-Object PrinterName, DocumentName, JobStatus", as_json=True) or "Kuyruk boş."
    return ps("Get-Printer | Select-Object Name, PrinterStatus, Default", as_json=True)


def print_file(path):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    os.startfile(str(p), "print")  # type: ignore[attr-defined]
    return f"Yazdırmaya gönderildi: {p.name}"


def usb_devices():
    return ps("Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*' -and $_.Class -ne 'USB'} | Select-Object FriendlyName, Class, Status", as_json=True)


def drives():
    if not psutil:
        return "psutil yok"
    out = []
    for p in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(p.mountpoint)
            out.append({"sürücü": p.mountpoint, "tür": p.fstype, "toplam_gb": round(u.total / 1e9), "boş_gb": round(u.free / 1e9), "dolu_%": u.percent})
        except Exception:
            pass
    return out


def startup_programs(action="list", name=""):
    name = _safe(name)
    if action == "disable" and name:
        r = ps(f"$k='HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run'; $v=(Get-ItemProperty $k).PSObject.Properties | ?{{$_.Name -like '*{name}*'}} | Select -First 1; "
               f"if($v){{ New-Item -Path 'HKCU:\\Software\\JARVIS\\DisabledStartup' -Force|Out-Null; Set-ItemProperty 'HKCU:\\Software\\JARVIS\\DisabledStartup' -Name $v.Name -Value $v.Value; Remove-ItemProperty $k -Name $v.Name; 'ok:'+$v.Name }} else {{ 'yok' }}")
        return f"Başlangıçtan kaldırıldı: {r[3:]} (geri almak için: startup_programs enable)" if r.startswith("ok:") else "Sadece kullanıcı başlangıç kayıtları değiştirilebilir; bulunamadı. Görev Yöneticisi > Başlangıç'tan da kapatabilirsin."
    if action == "enable" and name:
        r = ps(f"$d='HKCU:\\Software\\JARVIS\\DisabledStartup'; $v=(Get-ItemProperty $d -ErrorAction SilentlyContinue).PSObject.Properties | ?{{$_.Name -like '*{name}*'}} | Select -First 1; "
               f"if($v){{ Set-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name $v.Name -Value $v.Value; Remove-ItemProperty $d -Name $v.Name; 'ok' }} else {{ 'yok' }}")
        return "Başlangıca geri eklendi." if r == "ok" else "Bulunamadı."
    return ps("Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location", as_json=True)


def installed_programs(query=""):
    query = _safe(query)
    flt = f"| Where-Object DisplayName -like '*{query}*'" if query else ""
    return ps("Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, "
              "HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, "
              f"HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* {flt} | Where-Object DisplayName | "
              "Select-Object DisplayName, DisplayVersion | Sort-Object DisplayName | Select-Object -First 80", as_json=True)


# ===================== donanım =====================
def hardware_status():
    out = {}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            n, u, mu, mt, t = [x.strip() for x in r.stdout.splitlines()[0].split(",")]
            out["gpu"] = {"ad": n, "kullanım_%": u, "vram_mb": f"{mu}/{mt}", "sıcaklık_c": t}
    except Exception:
        pass
    if IS_WIN:
        if "gpu" not in out:
            try:
                v = ps("(((Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples | Measure-Object CookedValue -Sum).Sum)")
                name = ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name")
                out["gpu"] = {"ad": name, "kullanım_%": round(float(v.replace(",", ".")), 1) if v else None}
            except Exception:
                pass
        try:
            t = ps("Get-CimInstance -Namespace root/WMI -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | ForEach-Object { [math]::Round($_.CurrentTemperature/10-273.15,1) }")
            out["sıcaklık_c"] = t.split() if t and "erişim" not in t.lower() and "denied" not in t.lower() else "okunamadı (yönetici izni veya sensör desteği gerekebilir)"
        except Exception:
            out["sıcaklık_c"] = "okunamadı"
        try:
            out["fan"] = ps("Get-CimInstance Win32_Fan -ErrorAction SilentlyContinue | Select-Object Name, Status", as_json=True) or "sensör desteği yok"
        except Exception:
            pass
        try:
            out["diskler"] = ps("Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, @{n='GB';e={[math]::Round($_.Size/1GB)}}", as_json=True)
        except Exception:
            pass
    if psutil:
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            if temps:
                out["sensörler"] = {k: [round(x.current) for x in v] for k, v in temps.items()}
        except Exception:
            pass
        out["cpu_frekans_mhz"] = int(psutil.cpu_freq().current) if psutil.cpu_freq() else None
    return out


def diagnose_slowness():
    """Bilgisayar neden yavaş? Hızlı teşhis raporu."""
    from ..tools import system_status, top_processes
    rep = {"durum": system_status(), "cpu_en_çok": top_processes(6, "cpu"), "ram_en_çok": top_processes(6, "ram")}
    if psutil:
        try:
            rep["başlangıç_programı_sayısı"] = len(startup_programs()) if IS_WIN else None
        except Exception:
            pass
        d = psutil.disk_usage("C:\\" if IS_WIN else "/")
        tips = []
        if d.percent > 90:
            tips.append("Disk %90'dan dolu: büyük ve yinelenen dosyaları temizle.")
        if psutil.virtual_memory().percent > 85:
            tips.append("RAM çok dolu: en çok RAM kullanan programları kapat.")
        if psutil.cpu_percent(interval=0.5) > 80:
            tips.append("İşlemci yükü yüksek: en çok CPU kullanan işleme bak.")
        rep["öneriler"] = tips or ["Belirgin bir darboğaz görünmüyor."]
    return rep


# ===================== dosya işleri =====================
def find_duplicates(root="", min_kb=100, limit=30):
    base = _path(root)
    by_size = defaultdict(list)
    t0 = time.time()
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if not d.startswith(".") and d not in ("node_modules", "AppData", "Windows", "$Recycle.Bin")]
        for f in fns:
            fp = os.path.join(dp, f)
            try:
                s = os.path.getsize(fp)
                if s >= int(min_kb) * 1024:
                    by_size[s].append(fp)
            except Exception:
                pass
        if time.time() - t0 > 40:
            break
    groups = []
    for size, files in by_size.items():
        if len(files) < 2:
            continue
        hashes = defaultdict(list)
        for fp in files:
            try:
                h = hashlib.md5()
                with open(fp, "rb") as fh:
                    h.update(fh.read(1 << 20))
                    fh.seek(max(0, size - (1 << 20)))
                    h.update(fh.read(1 << 20))
                hashes[h.hexdigest()].append(fp)
            except Exception:
                pass
        for fl in hashes.values():
            if len(fl) > 1:
                groups.append({"boyut_mb": round(size / 1e6, 1), "dosyalar": fl})
    groups.sort(key=lambda g: g["boyut_mb"] * len(g["dosyalar"]), reverse=True)
    wasted = sum(g["boyut_mb"] * (len(g["dosyalar"]) - 1) for g in groups)
    return {"boşa_giden_mb": round(wasted), "gruplar": groups[: int(limit)]} if groups else "Yinelenen dosya bulunamadı."


def organize_folder(path="indirilenler", dry_run=True):
    cats = {"Resimler": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".svg"},
            "Videolar": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
            "Müzik": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
            "Belgeler": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".csv", ".ppt", ".pptx"},
            "Arşivler": {".zip", ".rar", ".7z", ".tar", ".gz"},
            "Programlar": {".exe", ".msi", ".bat", ".apk"},
            "Kod": {".py", ".js", ".html", ".css", ".json", ".java", ".cpp", ".c", ".cs", ".ts"}}
    base = _path(path)
    plan = defaultdict(list)
    for f in base.iterdir():
        if f.is_file():
            for cat, exts in cats.items():
                if f.suffix.lower() in exts:
                    plan[cat].append(f)
                    break
            else:
                plan["Diğer"].append(f)
    if str(dry_run).lower() in ("true", "1", "yes", "evet"):
        return {"klasör": str(base), "plan": {k: len(v) for k, v in plan.items()},
                "not": "Önizleme. Uygulamak için dry_run=false ile tekrar çağır."}
    moves = []
    for cat, files in plan.items():
        d = base / cat
        d.mkdir(exist_ok=True)
        for f in files:
            dst = d / f.name
            if dst.exists():
                dst = d / f"{f.stem}_{int(time.time())}{f.suffix}"
            shutil.move(str(f), str(dst))
            moves.append((str(f), str(dst)))
    try:
        from .control import journal
        journal("organize", moves=moves)
    except Exception:
        pass
    return f"{len(moves)} dosya kategorilere ayrıldı: {base} (geri alınabilir)"


def zip_files(paths, output=""):
    items = [_path(p.strip()) for p in str(paths).split(",") if p.strip()]
    out = _path(output) if output else items[0].with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for it in items:
            if it.is_dir():
                for fp in it.rglob("*"):
                    if fp.is_file():
                        z.write(fp, fp.relative_to(it.parent))
            elif it.exists():
                z.write(it, it.name)
    return f"Arşiv oluşturuldu: {out} ({out.stat().st_size // 1024} KB)"


def unzip_file(path, dest=""):
    p = _path(path)
    d = _path(dest) if dest else p.with_suffix("")
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():  # zip slip koruması
            if not os.path.abspath(os.path.join(d, n)).startswith(os.path.abspath(d)):
                return "Güvensiz arşiv (dışarı yazmaya çalışıyor), açılmadı."
        z.extractall(d)
    return f"Açıldı: {d}"


def backup_folder(path, dest=""):
    src = _path(path)
    target_dir = _path(dest) if dest else _path("belgeler") / "JARVIS_Yedekler"
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"{src.name}_{time.strftime('%Y%m%d_%H%M')}.zip"
    return zip_files(str(src), str(out))


def disk_cleanup_report():
    rep = {}
    for name, p in (("temp", os.environ.get("TEMP", "")), ("indirilenler", str(_path("indirilenler")))):
        if p and os.path.isdir(p):
            total = 0
            for dp, _, fns in os.walk(p):
                for f in fns:
                    try:
                        total += os.path.getsize(os.path.join(dp, f))
                    except Exception:
                        pass
            rep[name + "_mb"] = round(total / 1e6)
    rep["not"] = "Geçici dosyaları temizlemek için clean_temp aracını kullan."
    return rep


def clean_temp():
    p = os.environ.get("TEMP", "")
    if not p:
        return "TEMP klasörü yok."
    freed = 0
    for f in os.listdir(p):
        fp = os.path.join(p, f)
        try:
            if time.time() - os.path.getmtime(fp) < 86400:
                continue  # son 1 günü koru
            size = os.path.getsize(fp) if os.path.isfile(fp) else 0
            (shutil.rmtree if os.path.isdir(fp) else os.remove)(fp)
            freed += size
        except Exception:
            pass
    return f"Geçici dosyalar temizlendi, ~{round(freed / 1e6)} MB boşaldı."


# ===================== güvenlik =====================
def security_status():
    out = {}
    try:
        d = ps("Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated, QuickScanAge, FullScanAge", as_json=True)
        out["defender"] = d[0] if isinstance(d, list) and d else d
    except Exception as e:
        out["defender"] = str(e)
    try:
        out["güvenlik_duvarı"] = ps("Get-NetFirewallProfile | Select-Object Name, Enabled", as_json=True)
    except Exception as e:
        out["güvenlik_duvarı"] = str(e)
    try:
        out["son_tehditler"] = ps("Get-MpThreatDetection | Select-Object -First 5 InitialDetectionTime, ThreatID, ActionSuccess", as_json=True) or "yok"
    except Exception:
        pass
    try:
        out["windows_güncelleme_son"] = ps("(Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn")
    except Exception:
        pass
    return out


def defender_scan(kind="quick"):
    ps(f"Start-MpScan -ScanType {'FullScan' if kind == 'full' else 'QuickScan'} -AsJob | Out-Null", timeout=15)
    return f"Windows Defender {'tam' if kind == 'full' else 'hızlı'} tarama başlatıldı (arka planda)."


def suspicious_check():
    """Şüpheli işlemler ve ağ bağlantıları için sezgisel tarama."""
    if not psutil:
        return "psutil yok"
    sus_dirs = ("\\appdata\\local\\temp", "\\downloads\\", "\\indirilenler\\", "/tmp/", "\\public\\")
    procs, conns = [], []
    for p in psutil.process_iter(["pid", "name", "exe", "username"]):
        try:
            exe = (p.info["exe"] or "").lower()
            if any(d in exe for d in sus_dirs):
                procs.append({"ad": p.info["name"], "pid": p.info["pid"], "yol": p.info["exe"], "neden": "geçici/indirme klasöründen çalışıyor"})
        except Exception:
            pass
    common = {80, 443, 53, 123, 993, 587, 465, 5228, 3478, 8080}
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.raddr and c.status == "ESTABLISHED" and c.raddr.port not in common:
                try:
                    name = psutil.Process(c.pid).name() if c.pid else "?"
                except Exception:
                    name = "?"
                conns.append({"program": name, "hedef": f"{c.raddr.ip}:{c.raddr.port}"})
    except Exception:
        conns.append("Ağ bağlantılarını görmek için yönetici izni gerekebilir.")
    listen = []
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status == "LISTEN" and c.laddr.ip in ("0.0.0.0", "::"):
                try:
                    name = psutil.Process(c.pid).name() if c.pid else "?"
                except Exception:
                    name = "?"
                listen.append(f"{name}:{c.laddr.port}")
    except Exception:
        pass
    return {"şüpheli_konumdan_çalışan": procs[:20] or "yok",
            "alışılmadık_portlara_bağlantılar": conns[:25] or "yok",
            "dışarıya_açık_portlar": sorted(set(listen))[:30],
            "not": "Bu bir ön tarama; şüpheli görünen her şey zararlı değildir."}


_watch_state = {}


def watch_folder(path, action="start"):
    """Klasördeki değişiklikleri izler (yeni / silinen / değişen dosya)."""
    p = str(_path(path))
    snap = {}
    for dp, _, fns in os.walk(p):
        for f in fns:
            fp = os.path.join(dp, f)
            try:
                snap[fp] = os.path.getmtime(fp)
            except Exception:
                pass
    if action == "start" or p not in _watch_state:
        _watch_state[p] = snap
        return f"İzleme başladı: {p} ({len(snap)} dosya). Değişiklikleri görmek için action=check."
    old = _watch_state[p]
    new = [f for f in snap if f not in old]
    gone = [f for f in old if f not in snap]
    changed = [f for f in snap if f in old and snap[f] != old[f]]
    _watch_state[p] = snap
    return {"yeni": new[:30], "silinen": gone[:30], "değişen": changed[:30]}


TOOLS = {
    "brightness": (brightness, _schema("Ekran parlaklığını okur veya ayarlar (0-100).", {"level": N("yeni seviye")}), False),
    "wifi_status": (wifi_status, _schema("Wi-Fi bağlantısı ve çevredeki ağlar."), False),
    "wifi_toggle": (wifi_toggle, _schema("Wi-Fi'ı açar/kapatır.", {"on": {"type": "boolean"}}), True),
    "network_info": (network_info, _schema("IP, ağ bağdaştırıcıları ve internet gecikmesi."), False),
    "bluetooth_devices": (bluetooth_devices, _schema("Bluetooth cihazları."), False),
    "bluetooth_toggle": (bluetooth_toggle, _schema("Bluetooth'u açar/kapatır.", {"on": {"type": "boolean"}}), False),
    "printers": (printers, _schema("Yazıcıları listeler, kuyruğu gösterir veya varsayılanı ayarlar.",
                                   {"action": {"type": "string", "enum": ["list", "queue", "default"]}, "name": S("yazıcı adı")}), False),
    "print_file": (print_file, _schema("Dosyayı varsayılan yazıcıdan yazdırır.", {"path": S("dosya")}, ["path"]), True),
    "usb_devices": (usb_devices, _schema("Takılı USB cihazları."), False),
    "drives": (drives, _schema("Diskler ve doluluk."), False),
    "startup_programs": (startup_programs, _schema("Başlangıç programlarını listeler, kapatır (disable) veya geri açar (enable).",
                                                   {"action": {"type": "string", "enum": ["list", "disable", "enable"]}, "name": S("program")}),
                         lambda a: a.get("action") in ("disable", "enable")),
    "installed_programs": (installed_programs, _schema("Kurulu programlar.", {"query": S("ara")}), False),
    "hardware_status": (hardware_status, _schema("GPU kullanımı, sıcaklıklar, fan, disk sağlığı."), False),
    "diagnose_slowness": (diagnose_slowness, _schema("Bilgisayar neden yavaş? Teşhis ve öneriler."), False),
    "find_duplicates": (find_duplicates, _schema("Yinelenen dosyaları bulur.", {"root": S("klasör"), "min_kb": N("en küçük KB")}), False),
    "organize_folder": (organize_folder, _schema("Klasördeki dosyaları türlerine göre alt klasörlere ayırır. Önce dry_run=true ile önizle.",
                                                 {"path": S("klasör"), "dry_run": {"type": "boolean"}}),
                        lambda a: str(a.get("dry_run", True)).lower() not in ("true", "1")),
    "zip_files": (zip_files, _schema("Dosya/klasörleri zip yapar.", {"paths": S("yollar, virgülle"), "output": S("çıktı .zip")}, ["paths"]), False),
    "unzip_file": (unzip_file, _schema("Zip açar.", {"path": S("zip"), "dest": S("hedef klasör")}, ["path"]), False),
    "backup_folder": (backup_folder, _schema("Klasörü tarihli zip olarak yedekler.", {"path": S("klasör"), "dest": S("yedek yeri")}, ["path"]), False),
    "disk_cleanup_report": (disk_cleanup_report, _schema("Temizlenebilir alan raporu."), False),
    "clean_temp": (clean_temp, _schema("1 günden eski geçici dosyaları siler."), True),
    "security_status": (security_status, _schema("Defender, güvenlik duvarı, son tehditler, son güncelleme."), False),
    "defender_scan": (defender_scan, _schema("Defender taraması başlatır.", {"kind": {"type": "string", "enum": ["quick", "full"]}}), False),
    "suspicious_check": (suspicious_check, _schema("Şüpheli işlem ve ağ bağlantısı taraması."), False),
    "watch_folder": (watch_folder, _schema("Klasör değişikliklerini izler (start sonra check).",
                                           {"path": S("klasör"), "action": {"type": "string", "enum": ["start", "check"]}}, ["path"]), False),
}
