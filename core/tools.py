"""JARVIS'in elleri: bilgisayar, dosya, internet, medya, hafıza araçları.

Kritik araçlar (silme, kapatma, komut, üzerine yazma...) doğrudan çalışmaz;
kullanıcı arayüzden / Telegram'dan onay verince çalışır.
"""
import datetime as _dt
import fnmatch
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from . import memory
from .config import DATA

IS_WIN = sys.platform.startswith("win")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JarvisPersonalAI/1.0"
HOME = Path.home()

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None


def _http_get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(3_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "ignore")


def _path(p):
    p = os.path.expandvars(os.path.expanduser(str(p or "").strip().strip('"')))
    aliases = {
        "masaüstü": HOME / "Desktop", "masaustu": HOME / "Desktop", "desktop": HOME / "Desktop",
        "belgeler": HOME / "Documents", "documents": HOME / "Documents",
        "indirilenler": HOME / "Downloads", "downloads": HOME / "Downloads",
        "resimler": HOME / "Pictures", "müzik": HOME / "Music", "videolar": HOME / "Videos",
        "ev": HOME, "home": HOME, "": HOME,
    }
    low = p.lower()
    if low in aliases:
        return aliases[low]
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:", p):
        return Path(p)
    first, _, rest = p.replace("\\", "/").partition("/")
    if first and first.lower() in aliases and rest:
        return aliases[first.lower()] / rest
    return Path(p)


# ===================== SİSTEM =====================
def get_time():
    now = _dt.datetime.now()
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    return f"{now:%d.%m.%Y} {gunler[now.weekday()]}, saat {now:%H:%M}"


def system_status():
    if not psutil:
        return "psutil kurulu değil"
    vm = psutil.virtual_memory()
    out = {
        "işletim_sistemi": f"{platform.system()} {platform.release()}",
        "cpu_yüzde": psutil.cpu_percent(interval=0.4),
        "çekirdek": psutil.cpu_count(),
        "ram_yüzde": vm.percent,
        "ram_gb": f"{vm.used/1e9:.1f}/{vm.total/1e9:.1f}",
        "açık_kalma": str(_dt.timedelta(seconds=int(time.time() - psutil.boot_time()))),
    }
    try:
        root = "C:\\" if IS_WIN else "/"
        du = psutil.disk_usage(root)
        out["disk_yüzde"] = du.percent
        out["disk_boş_gb"] = round(du.free / 1e9, 1)
    except Exception:
        pass
    try:
        b = psutil.sensors_battery()
        if b:
            out["pil"] = f"%{int(b.percent)} {'şarjda' if b.power_plugged else 'pilde'}"
    except Exception:
        pass
    try:
        n = psutil.net_io_counters()
        out["ağ_mb"] = {"gönderilen": round(n.bytes_sent / 1e6), "alınan": round(n.bytes_recv / 1e6)}
    except Exception:
        pass
    return out


def top_processes(n=8, by="ram"):
    if not psutil:
        return "psutil yok"
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            procs.append(p)
            p.cpu_percent(None)
        except Exception:
            pass
    time.sleep(0.5)
    rows = []
    for p in procs:
        try:
            rows.append({"ad": p.info["name"], "pid": p.info["pid"],
                         "ram_mb": round(p.info["memory_info"].rss / 1e6) if p.info["memory_info"] else 0,
                         "cpu": p.cpu_percent(None)})
        except Exception:
            pass
    key = "cpu" if by == "cpu" else "ram_mb"
    rows.sort(key=lambda r: r[key], reverse=True)
    return rows[: int(n)]


APPS = {
    "chrome": "chrome", "google chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "not defteri": "notepad", "notepad": "notepad", "hesap makinesi": "calc",
    "calculator": "calc", "dosya gezgini": "explorer", "explorer": "explorer", "paint": "mspaint",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt", "outlook": "outlook",
    "spotify": "spotify:", "discord": "discord:", "whatsapp": "whatsapp:", "telegram": "tg:",
    "steam": "steam:", "vlc": "vlc", "vs code": "code", "vscode": "code", "visual studio code": "code",
    "cmd": "cmd", "komut istemi": "cmd", "powershell": "powershell", "terminal": "wt",
    "ayarlar": "ms-settings:", "settings": "ms-settings:", "görev yöneticisi": "taskmgr",
    "task manager": "taskmgr", "takvim": "outlookcal:", "kamera": "microsoft.windows.camera:",
    "mağaza": "ms-windows-store:", "saat": "ms-clock:", "hava durumu": "bingweather:",
}


def open_app(name):
    target = APPS.get(name.lower().strip(), name.strip())
    try:
        if IS_WIN:
            if target.endswith(":") or ":" in target and not os.path.exists(target):
                os.startfile(target)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(f'start "" "{target}"', shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", target])
        else:
            exe = shutil.which(target) or shutil.which(name)
            subprocess.Popen([exe] if exe else ["xdg-open", target])
        return f"'{name}' açılıyor."
    except Exception as e:
        return f"'{name}' açılamadı: {e}"


def close_app(name):
    if not psutil:
        return "psutil yok"
    target = APPS.get(name.lower().strip(), name.strip()).rstrip(":").lower()
    killed = 0
    for p in psutil.process_iter(["name"]):
        try:
            pn = (p.info["name"] or "").lower()
            if pn == target or pn == target + ".exe" or pn.startswith(target):
                p.terminate()
                killed += 1
        except Exception:
            pass
    return f"{killed} işlem kapatıldı." if killed else f"'{name}' çalışan işlem bulunamadı."


def open_url(url):
    if not re.match(r"^[a-z]+://", url):
        url = "https://" + url
    webbrowser.open(url)
    return f"Açıldı: {url}"


# ===================== MEDYA / GÜÇ (Windows tuşları) =====================
_VK = {"volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD, "play_pause": 0xB3,
       "next": 0xB0, "previous": 0xB1, "stop": 0xB2}


def _press(vk, times=1):
    import ctypes  # noqa
    for _ in range(max(1, times)):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.02)


def media_control(action, steps=5):
    action = action.lower()
    if action not in _VK:
        return f"Bilinmeyen eylem. Geçerli: {', '.join(_VK)}"
    if not IS_WIN:
        return "Medya tuşları şu an sadece Windows'ta destekleniyor."
    _press(_VK[action], int(steps) if action.startswith("volume") else 1)
    return f"Tamam: {action}"


def lock_pc():
    if IS_WIN:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Bilgisayar kilitlendi."
    return "Kilitleme sadece Windows'ta."


def power(action):
    action = action.lower()
    cmds = {
        "shutdown": "shutdown /s /t 10", "restart": "shutdown /r /t 10",
        "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0", "cancel": "shutdown /a",
    }
    if action not in cmds:
        return "Geçerli: shutdown, restart, sleep, cancel"
    if not IS_WIN:
        return "Güç komutları sadece Windows'ta."
    subprocess.Popen(cmds[action], shell=True)
    return f"{action} komutu verildi (kapatma/yeniden başlatma 10 sn içinde; iptal için 'cancel')."


def run_command(command):
    shell = ["powershell", "-NoProfile", "-Command", command] if IS_WIN else ["bash", "-lc", command]
    try:
        r = subprocess.run(shell, capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + (("\nHATA: " + r.stderr) if r.stderr else "")
        return out.strip()[:6000] or f"(çıktı yok, kod {r.returncode})"
    except Exception as e:
        return f"Komut çalışmadı: {e}"


def screenshot():
    try:
        from PIL import ImageGrab  # type: ignore
    except Exception:
        return "Ekran görüntüsü için 'pip install pillow' gerekli."
    d = DATA / "screens"
    d.mkdir(exist_ok=True)
    p = d / f"ekran_{time.strftime('%Y%m%d_%H%M%S')}.png"
    ImageGrab.grab(all_screens=True).save(p)
    return f"Kaydedildi: {p}"


def screenshot_to_phone():
    from . import telegram_bot
    return telegram_bot.screenshot_to_phone()


# ===================== DOSYALAR =====================
def list_dir(path=""):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    items = []
    for c in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:200]:
        try:
            items.append(("📁 " if c.is_dir() else "") + c.name + ("" if c.is_dir() else f" ({c.stat().st_size//1024} KB)"))
        except Exception:
            items.append(c.name)
    return {"klasör": str(p), "öğeler": items}


def find_files(pattern, root="", limit=30):
    base = _path(root)
    pat = pattern if any(ch in pattern for ch in "*?") else f"*{pattern}*"
    found = []
    t0 = time.time()
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "AppData", "$Recycle.Bin", "Windows")]
        for f in filenames + dirnames:
            if fnmatch.fnmatch(f.lower(), pat.lower()):
                found.append(os.path.join(dirpath, f))
                if len(found) >= int(limit):
                    return found
        if time.time() - t0 > 20:
            found.append("(arama 20 sn sınırında durduruldu)")
            break
    return found or "Bulunamadı."


def read_file(path, max_chars=8000):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    ext = p.suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader  # type: ignore
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages[:40])
        elif ext == ".docx":
            import docx  # type: ignore
            text = "\n".join(par.text for par in docx.Document(str(p)).paragraphs)
        elif ext in (".xlsx", ".xlsm"):
            import openpyxl  # type: ignore
            wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
            lines = []
            for ws in wb.worksheets[:3]:
                lines.append(f"# {ws.title}")
                for row in ws.iter_rows(max_row=100, values_only=True):
                    lines.append("\t".join("" if v is None else str(v) for v in row))
            text = "\n".join(lines)
        else:
            text = p.read_text(encoding="utf-8", errors="ignore")
    except ImportError as e:
        return f"Bu dosya türü için ek paket gerekli ({e.name}). requirements-extra.txt'yi kurun."
    return text[: int(max_chars)] + ("\n...(kısaltıldı)" if len(text) > int(max_chars) else "")


def write_file(path, content):
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if p.exists():
        bdir = DATA / "geri_alma"
        bdir.mkdir(exist_ok=True)
        backup = str(bdir / f"{int(time.time()*1000)}_{p.name}")
        shutil.copyfile(p, backup)
    p.write_text(content, encoding="utf-8")
    _journal("write", path=str(p), backup=backup)
    return f"Yazıldı: {p} ({len(content)} karakter)"


def _journal(op, **kw):
    try:
        from .skills.control import journal
        journal(op, **kw)
    except Exception:
        pass


def move_file(src, dst):
    s, d = _path(src), _path(dst)
    d.parent.mkdir(parents=True, exist_ok=True)
    final = shutil.move(str(s), str(d))
    _journal("move", src=str(s), dst=str(final))
    return f"Taşındı: {s} → {final} (geri alınabilir)"


def delete_file(path):
    """Kalıcı silmez: JARVIS çöp kutusuna taşır, 'geri al' ile geri gelir."""
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    trash = DATA / "cop_kutusu"
    trash.mkdir(exist_ok=True)
    dst = trash / f"{int(time.time()*1000)}_{p.name}"
    shutil.move(str(p), str(dst))
    _journal("delete", src=str(p), trash=str(dst))
    return f"Silindi (JARVIS çöp kutusunda, 'geri al' diyerek geri getirebilirsin): {p.name}"


def big_files(root="", min_mb=200, limit=20):
    base = _path(root)
    out = []
    t0 = time.time()
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("Windows", "$Recycle.Bin")]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                s = os.path.getsize(fp)
                if s >= min_mb * 1e6:
                    out.append((s, fp))
            except Exception:
                pass
        if time.time() - t0 > 25:
            break
    out.sort(reverse=True)
    return [f"{s/1e9:.2f} GB  {fp}" for s, fp in out[: int(limit)]] or "Büyük dosya yok."


# ===================== İNTERNET =====================
# ---- canlı arama: birden çok kaynak, biri engellenirse diğeri (hepsi ücretsiz, anahtarsız) ----
def _clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _bing_url(href):
    """Bing bazen linki /ck/a?...&u=a1<base64> içine sarar; gerçek adresi çıkar."""
    if "bing.com/ck/a" in href and "u=a1" in href:
        import base64
        enc = urllib.parse.unquote(href.split("u=a1", 1)[1].split("&", 1)[0])
        try:
            return base64.urlsafe_b64decode(enc + "=" * (-len(enc) % 4)).decode("utf-8", "ignore")
        except Exception:
            return href
    return html.unescape(href)


def _search_bing(query, n):
    page = _http_get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "setlang": "tr", "cc": "TR", "count": 15}))
    out = []
    for blk in re.findall(r'<li class="b_algo"(.*?)</li>', page, re.S):
        m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not m:
            continue
        sn = re.search(r'<p[^>]*>(.*?)</p>', blk, re.S) or re.search(r'class="b_caption"[^>]*>(.*?)</div>', blk, re.S)
        out.append({"başlık": _clean(m.group(2)), "özet": _clean(sn.group(1) if sn else ""), "link": _bing_url(m.group(1))})
        if len(out) >= n:
            break
    return out


def _search_ddg(query, n):
    req = urllib.request.Request("https://html.duckduckgo.com/html/", data=urllib.parse.urlencode({"q": query, "kl": "tr-tr"}).encode(),
                                 headers={"User-Agent": UA, "Accept-Language": "tr,en;q=0.8", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=12) as r:
        page = r.read(2_000_000).decode("utf-8", "ignore")
    if "anomaly" in page and "result__a" not in page:
        raise RuntimeError("DuckDuckGo robot doğrulaması istedi")
    out = []
    for href, title, snip in re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:class="result__snippet"[^>]*>(.*?)</a>)?', page, re.S):
        if "uddg=" in href:
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        if "duckduckgo.com/y.js" in href:  # reklam
            continue
        out.append({"başlık": _clean(title), "özet": _clean(snip), "link": href})
        if len(out) >= n:
            break
    return out


def _search_ddg_lite(query, n):
    page = _http_get("https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query, "kl": "tr-tr"}))
    links = re.findall(r"<a[^>]+href=\"([^\"]+)\"[^>]*class=['\"]result-link['\"][^>]*>(.*?)</a>", page, re.S)
    snips = re.findall(r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", page, re.S)
    out = []
    for i, (href, title) in enumerate(links):
        if "uddg=" in href:
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        out.append({"başlık": _clean(title), "özet": _clean(snips[i] if i < len(snips) else ""), "link": href})
        if len(out) >= n:
            break
    return out


def news_search(query, max_results=8):
    """Google Haberler (canlı, tarihli). Anahtar gerekmez."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    raw = _http_get("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "tr", "gl": "TR", "ceid": "TR:tr"}))
    out = []
    for it in ET.fromstring(raw.encode("utf-8")).iter("item"):
        when = it.findtext("pubDate") or ""
        try:
            when = parsedate_to_datetime(when).astimezone().strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass
        out.append({"başlık": _clean(it.findtext("title")), "kaynak": _clean(it.findtext("source")), "tarih": when, "link": it.findtext("link") or ""})
        if len(out) >= int(max_results):
            break
    return out or "Haber bulunamadı."


def _grounded(query):
    """Gemini + Google Arama (canlı): kısa güncel cevap + kaynaklar. Ücretsiz kotası dolarsa sessizce atlanır."""
    from . import llm
    if not llm.configured("gemini") or llm.key_bad("gemini"):
        return None
    tried = []
    avail = set(llm.list_models("gemini"))
    has_light = any(m in avail for m in llm.PROVIDERS["gemini"]["light"])
    # hafif model varsa yalnızca onu kullan (kotası dolduysa canlı cevabı atla; sohbetin 3.8 hakkı yenmesin)
    for model in ((llm.light_model("gemini"),) if has_light else (llm.pick_model("gemini"),)):
        if not model or model in tried or llm.cooling("gemini", model):
            continue
        tried.append(model)
        body = {"contents": [{"role": "user", "parts": [{"text": f"Bugün {time.strftime('%d.%m.%Y')}. Google'da arayıp EN GÜNCEL bilgiyle, "
                                                                  f"tarih belirterek kısa Türkçe cevapla: {query}"}]}],
                "tools": [{"google_search": {}}]}
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                     data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": llm._key("gemini")})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "ignore")
            if llm.report_bad_key("gemini", e.code, b):
                return None
            if e.code == 429:
                llm.mark_exhausted("gemini", model, b)
            continue
        except Exception:
            continue
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", [])).strip()
        meta = cand.get("groundingMetadata") or {}
        srcs = [{"başlık": (c.get("web") or {}).get("title", ""), "link": (c.get("web") or {}).get("uri", "")} for c in meta.get("groundingChunks", [])][:6]
        if text:
            return {"kaynak": "Google Arama (canlı, Gemini)", "cevap": text, "kaynaklar": srcs}
    return None


_NEWSY = re.compile(r"haber|son dakika|bugün|dün|şu an|şimdi|güncel|en son|en yeni|son durum|maç|skor|seçim|deprem|fiyat|kur|borsa|"
                    r"\b20[2-3]\d\b|news|latest|today", re.I)


def web_search(query, max_results=6, recent=False):
    """Canlı web araması — tüm kaynaklar AYNI ANDA sorulur, en fazla ~12 sn beklenir:
    Gemini+Google (canlı cevap), Bing, DuckDuckGo, DuckDuckGo Lite, Google Haberler."""
    from concurrent.futures import ThreadPoolExecutor, wait
    n = int(max_results)
    want_news = recent or bool(_NEWSY.search(query))
    jobs = {"canlı": lambda: _grounded(query), "bing": lambda: _search_bing(query, n),
            "duckduckgo": lambda: _search_ddg(query, n), "duckduckgo-lite": lambda: _search_ddg_lite(query, n),
            "haberler": lambda: news_search(query, 6)}
    ex = ThreadPoolExecutor(max_workers=len(jobs))
    futs = {ex.submit(fn): name for name, fn in jobs.items()}
    t0 = time.time()
    done, _ = wait(futs, timeout=6)
    have_web = lambda: any(futs_name in ("bing", "duckduckgo", "duckduckgo-lite") and f.done() and not f.exception() and f.result()
                           for f, futs_name in futs.items())
    # canlı Google cevabı birkaç saniye daha sürebilir; web sonucu yoksa ya da canlı cevap bekleniyorsa biraz daha bekle
    if time.time() - t0 < 12:
        pending = [f for f in futs if not f.done() and (futs[f] == "canlı" or not have_web())]
        if pending:
            wait(pending, timeout=12 - (time.time() - t0))
    ex.shutdown(wait=False, cancel_futures=True)
    res, errors = {}, []
    for f, name in futs.items():
        if not f.done():
            errors.append(f"{name}: zaman aşımı")
            continue
        if f.exception():
            errors.append(f"{name}: {str(f.exception())[:60]}")
            continue
        res[name] = f.result()
    out = {}
    if res.get("canlı"):
        out["canlı_cevap"] = res["canlı"]
    for name in ("bing", "duckduckgo", "duckduckgo-lite"):
        if res.get(name):
            out["motor"], out["sonuçlar"] = name, res[name]
            break
    if isinstance(res.get("haberler"), list) and res["haberler"] and (want_news or "sonuçlar" not in out):
        out["haberler"] = res["haberler"]
    if not out:
        return "Arama yapılamadı (" + "; ".join(errors) + "). İnternet bağlantısını kontrol et."
    out["not"] = (f"Bugün {time.strftime('%d.%m.%Y')}. Bu sonuçlar CANLI; kendi eski bilginle çelişirse bunlara güven. "
                  "Cevap için genelde bu yeterli; gerekmedikçe başka arama yapma ya da sayfa açma.")
    return out


def read_webpage(url, max_chars=7000):
    try:
        page = _http_get(url)
    except Exception as e:
        return f"Sayfa açılamadı: {e}"
    page = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav).*?</\1>", " ", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text).strip()
    return text[: int(max_chars)]


def weather(city="Istanbul"):
    try:  # önce Open-Meteo (daha güvenilir), olmazsa wttr.in
        from .skills.hud import weather_full
        w = weather_full(city)
        return {"şehir": w["şehir"], "sıcaklık": f"{w['derece']}°C", "hissedilen": f"{w['hissedilen']}°C", "durum": w["durum"], "nem": f"{w['nem']}%",
                "rüzgar_kmh": w["rüzgar"], "yağmur_ihtimali": f"%{w['yağmur']}", "3_gün": [{"tarih": d["tarih"], "min": d["min"], "max": d["max"], "durum": d["durum"]} for d in w["günler"][:3]]}
    except Exception:
        pass
    try:
        data = json.loads(_http_get(f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=tr"))
        cur = data["current_condition"][0]
        desc = (cur.get("lang_tr") or cur.get("weatherDesc") or [{"value": ""}])[0]["value"]
        days = [{"tarih": d["date"], "min": d["mintempC"], "max": d["maxtempC"]} for d in data.get("weather", [])[:3]]
        return {"şehir": city, "sıcaklık": cur["temp_C"] + "°C", "hissedilen": cur["FeelsLikeC"] + "°C",
                "durum": desc, "nem": cur["humidity"] + "%", "rüzgar_kmh": cur["windspeedKmph"], "3_gün": days}
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"


def currency(base="USD", targets="TRY,EUR,GBP"):
    try:
        data = json.loads(_http_get(f"https://open.er-api.com/v6/latest/{base.upper()}"))
        rates = data.get("rates", {})
        return {"baz": base.upper(), "güncelleme": data.get("time_last_update_utc"),
                **{t: rates.get(t.upper()) for t in targets.replace(" ", "").split(",")}}
    except Exception as e:
        return f"Kur alınamadı: {e}"


# ===================== HAFIZA / ZAMANLAYICI =====================
def remember(fact, category="genel"):
    fid = memory.add_fact(fact, category)
    return f"Hafızaya kaydedildi (#{fid})."


def forget(text):
    n = memory.forget_matching(text)
    return f"{n} kayıt silindi."


def recall(query):
    f = memory.find_facts(query)
    m = memory.search_messages(query, 6)
    return {"bilgiler": [x["fact"] for x in f], "eski_konuşmalar": [f"{x['role']}: {x['content'][:200]}" for x in m]}


def set_reminder(minutes, text):
    due = time.time() + float(minutes) * 60
    memory.add_reminder(text, due)
    return f"{float(minutes):g} dakika sonra hatırlatacağım: {text}"


def list_reminders():
    return [{"metin": r["text"], "zaman": _dt.datetime.fromtimestamp(r["due"]).strftime("%d.%m %H:%M")}
            for r in memory.pending_reminders()] or "Bekleyen hatırlatıcı yok."


def backup_memory():
    return f"Hafıza yedeklendi: {memory.backup()}"


# ===================== KAYIT =====================
def _schema(desc, props=None, required=None):
    return {"description": desc, "parameters": {"type": "object", "properties": props or {}, "required": required or []}}


S = lambda d: {"type": "string", "description": d}
N = lambda d: {"type": "number", "description": d}

TOOLS = {
    "get_time": (get_time, _schema("Şu anki tarih ve saat."), False),
    "system_status": (system_status, _schema("CPU, RAM, disk, pil, ağ durumu."), False),
    "top_processes": (top_processes, _schema("En çok kaynak tüketen programlar.",
                      {"n": N("kaç tane"), "by": {"type": "string", "enum": ["ram", "cpu"]}}), False),
    "open_app": (open_app, _schema("Program veya uygulama açar (chrome, spotify, word, ayarlar...).",
                 {"name": S("uygulama adı")}, ["name"]), False),
    "close_app": (close_app, _schema("Çalışan bir programı kapatır.", {"name": S("program adı")}, ["name"]), True),
    "open_url": (open_url, _schema("Tarayıcıda web adresi açar (YouTube araması vb. için de).",
                 {"url": S("adres")}, ["url"]), False),
    "media_control": (media_control, _schema("Müzik/medya ve ses seviyesi kontrolü.",
                      {"action": {"type": "string", "enum": list(_VK)}, "steps": N("ses için adım (1 adım=%2)")},
                      ["action"]), False),
    "lock_pc": (lock_pc, _schema("Bilgisayarı kilitler."), False),
    "power": (power, _schema("Bilgisayarı kapatır / yeniden başlatır / uyutur.",
              {"action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "cancel"]}}, ["action"]),
              lambda a: a.get("action") != "cancel"),
    "run_command": (run_command, _schema("PowerShell (Windows) komutu çalıştırır. Başka araç yetmezse kullan.",
                    {"command": S("komut")}, ["command"]), True),
    "screenshot": (screenshot, _schema("Ekran görüntüsü alıp kaydeder."), False),
    "screenshot_to_phone": (screenshot_to_phone, _schema("Ekran görüntüsünü alıp Telegram ile telefona gönderir."), False),
    "list_dir": (list_dir, _schema("Klasör içeriğini listeler (masaüstü, belgeler, indirilenler veya tam yol).",
                 {"path": S("klasör")}), False),
    "find_files": (find_files, _schema("Dosya/klasör arar.", {"pattern": S("ad veya *.pdf gibi desen"),
                   "root": S("nerede aranacak"), "limit": N("en fazla")}, ["pattern"]), False),
    "big_files": (big_files, _schema("Büyük dosyaları bulur.", {"root": S("klasör"), "min_mb": N("MB")}), False),
    "read_file": (read_file, _schema("Dosya içeriğini okur (txt, kod, pdf, docx, xlsx).", {"path": S("yol")}, ["path"]), False),
    "write_file": (write_file, _schema("Dosya oluşturur/yazar.", {"path": S("yol"), "content": S("içerik")},
                   ["path", "content"]), lambda a: _path(a.get("path", "")).exists()),
    "move_file": (move_file, _schema("Dosya taşır / yeniden adlandırır.", {"src": S("kaynak"), "dst": S("hedef")},
                  ["src", "dst"]), True),
    "delete_file": (delete_file, _schema("Dosyayı geri dönüşüm kutusuna gönderir.", {"path": S("yol")}, ["path"]), True),
    "news_search": (news_search, _schema("Google Haberler'de CANLI haber arar (tarihli, kaynaklı).", {"query": S("konu"), "max_results": N("adet")}, ["query"]), False),
    "web_search": (web_search, _schema("İnternette CANLI arar (Google/Bing/DuckDuckGo + haberler). Güncel olabilecek HER şey için önce bunu kullan: haber, fiyat, kişi, sürüm, skor, etkinlik, 'en son/en yeni'.",
                   {"query": S("arama")}, ["query"]), False),
    "read_webpage": (read_webpage, _schema("Bir web sayfasının metnini okur.", {"url": S("adres")}, ["url"]), False),
    "weather": (weather, _schema("Hava durumu (kısa). Ekranda büyük panel için weather_panel.", {"city": S("şehir")}), False),
    "currency": (currency, _schema("Döviz kurları.", {"base": S("baz para, örn USD"), "targets": S("TRY,EUR")}), False),
    "remember": (remember, _schema("Kullanıcı hakkında kalıcı bilgi kaydeder.",
                 {"fact": S("bilgi"), "category": S("kategori")}, ["fact"]), False),
    "forget": (forget, _schema("Hafızadan bilgi siler.", {"text": S("silinecek bilgi")}, ["text"]), False),
    "recall": (recall, _schema("Hafızada ve eski konuşmalarda arar.", {"query": S("ne")}, ["query"]), False),
    "set_reminder": (set_reminder, _schema("Hatırlatıcı kurar.", {"minutes": N("kaç dakika sonra"),
                     "text": S("ne hatırlatılacak")}, ["minutes", "text"]), False),
    "list_reminders": (list_reminders, _schema("Bekleyen hatırlatıcılar."), False),
    "backup_memory": (backup_memory, _schema("Hafızayı yedekler."), False),
}


# ===================== yetenek modülleri + akıllı araç seçimi =====================
from .skills import load_all as _load_skills  # noqa: E402

TOOL_GROUP = {name: "core" for name in TOOLS}
_skill_tools, _skill_groups = _load_skills()
TOOLS.update(_skill_tools)
TOOL_GROUP.update(_skill_groups)

GROUP_INFO = {
    "google": ("Gmail ve Google Takvim", "mail posta gmail gelen kutu ileti yanıtla cevapla taslak takvim toplantı randevu ajanda etkinlik davet meet program bugün yarın hafta"),
    "computer": ("ekranı görme, fare/klavye, pencereler, pano, kamera, görsel analiz", "ekran ekranda tıkla tıklat yaz klavye fare mouse pencere sekme pano kopyala yapıştır kamera bak gör görsel resim fotoğraf foto oku ocr buton hata mesajı kullan"),
    "windows": ("Windows/donanım/güvenlik/dosya bakımı", "parlaklık wifi wi-fi internet ağ bluetooth yazıcı yazdır usb disk sürücü başlangıç açılış program kurulu gpu ekran-kartı sıcaklık fan yavaş kasıyor donuyor yinelenen kopya zip arşiv sıkıştır yedek düzenle temizle güvenlik virüs defender tarama şüpheli güvenlik duvarı izle"),
    "office": ("Word, Excel, PowerPoint, PDF, grafik, veri analizi", "word excel powerpoint sunum slayt pdf belge doküman rapor tablo grafik çizelge analiz veri csv birleştir dönüştür karşılaştır fatura dilekçe cv özgeçmiş fatura proforma kdv"),
    "finance": ("altın, döviz, borsa, kripto, bütçe", "altın gram çeyrek borsa hisse bist dolar euro kur döviz bitcoin kripto fiyat alarm harcama harcadım gider gelir maaş bütçe para ödeme portföy yatırım strateji geri test backtest risk oynaklık monte carlo emeklilik birikim kredi taksit faiz konut mortgage hedef"),
    "automation": ("zamanlanmış görevler, yapılacaklar, brifing, kendi testleri, hafıza yedekleri", "görev zamanla her gün her sabah her akşam her hafta otomatik planla yapılacak liste todo iş ekle son tarih brifing günlük özet test sağlık yedek geri yükle hatırla"),
    "smarthome": ("akıllı ev, Arduino, robot, 3D yazıcı", "ışık lamba priz klima termostat televizyon tv perde kapı kilit ev senaryo sensör arduino raspberry robot motor seri 3d yazıcı süpürge"),
    "media": ("YouTube, Spotify, WhatsApp, Telegram, ses→yazı, video özeti", "youtube spotify şarkı müzik çal oynat video film whatsapp telegram mesaj kayıt yazıya transkript altyazı ortam sesleri dinle duman alarmı cam kırılması bebek ağlarsa kapı zili havlama"),
    "voiceid": ("ses kimliği", "sesimi sesinden tanı tanıyor kim konuşuyor"),
    "vault": ("şifre kasası", "şifre şifremi parola kasa giriş login oturum kullanıcı"),
    "habits": ("ekran süresi, alışkanlıklar, pano geçmişi, Windows bildirimleri", "süre ekran-süresi alışkanlık ne kadar zaman kullandım verimlilik pano kopyaladığım bildirim bildirimler"),
    "games": ("oyunlar: kütüphane, başlatma, FPS, performans", "oyun oyunu oyunlar steam epic fps oyna oynuyorum kasma lag performans obs yayın yayını kayıt kaydı kaydet sahne replay twitch youtube canlı"),
    "selfdev": ("kendini geliştirme: kendi kodu, eklenti yazma, güncelleme", "yetenek eklenti kodun kendini geliştir güncelle güncelleme sürüm yeni özellik plugin"),
    "geo": ("3D Dünya küresi, ülkeler, harita, uçuşlar, depremler, mesafe, tarih turu", "dünya dünyayı küre harita ülke ülkesi ülkeler kıta şehir nüfus yüzölçüm ekonomi gsyh uçuş uçak deprem gemi rota mesafe uzaklık km sokak uydu konum işaretle git uç tarih savaş fetih imparatorluk keşif başkent"),
    "holo": ("hologram atölyesi (3D tasarım), bilim simülasyonları, ekran modları, paneller", "hologram 3d tasarla tasarım model modeli bina ev araba araç robot roket köprü dron drone stl obj glb parçala döndür büyüt atölye laboratuvar bilim simülasyon güneş gezegen galaksi atom molekül fizik yerçekimi sarkaç atış çarpışma hava akışı devre direnç dna vücut organ grafik panel mod görünüm göster aç"),
    "control": ("acil durdurma, geri alma, program kur/kaldır, monitörler, pencere düzeni, Windows ayarları, gizlilik, ağ, robot kol", "acil dur durdur geri al geri program kur kaldır yükle güncelle winget monitör ekran pencere düzenle yan sanal masaüstü koyu tema duvar güç gizlilik kamera mikrofon izin ağ wifi modem cihazlar hız ping internet robot kol servo arduino sensör"),
    "daily": ("alarm, notlar, alışveriş listesi, haberler, kod projeleri, GitHub", "alarm uyandır not notlarım yaz kaydet alışveriş liste market haber haberler gündem manşet proje kod yaz program uygulama github depo commit push test"),
    "space": ("uzay: canlı güneş sistemi, gezegen konumları, uydular, ISS, gökyüzü, yıldızlar, Ay, Mars, kara delik, galaksi, uzay araçları", "uzay gezegen güneş ay mars jüpiter satürn venüs merkür uranüs neptün plüton yıldız takımyıldız gökyüzü gece uydu iss istasyon starlink türksat gps voyager webb hubble kara galaksi evren yörünge astronomi teleskop dolunay"),
    "worldwatch": ("canlı dünya takibi: doğal olaylar, yangınlar, fırtınalar, seller, volkanlar, uydu görüntüsü, yağış radarı, haber haritası, canlı gemiler", "yangın orman fırtına kasırga tayfun sel taşkın volkan yanardağ afet doğal olay radar yağmur yağış uydu görüntüsü haber haberler dünyada gündem gemi gemiler deniz trafiği ais liman boğaz"),
    "team": ("yapay zekâ ekibi: uzman ajanlar, plan, denetim, rapor", "ekip ekibe ekibi takım ajan ajanlar uzman uzmanlar görevlendir dağıt kapsamlı detaylı araştır rapor araştırma projesi"),
    "translate": ("çeviri: metin, çoklu dil, canlı sesli tercüman, altyazı", "çevir çeviri tercüme tercüman ingilizce almanca fransızca arapça rusça ispanyolca italyanca çince japonca korece dil altyazı srt translate"),
    "studio": ("görsel stüdyo: resim üret, fotoğraf düzenle, kolaj, logo, video analiz/kes/birleştir/montaj/gif", "resim görsel çiz illüstrasyon fotoğraf foto kolaj logo filigran video sahne montaj gif kırp kes birleştir hızlandır yavaşlat ffmpeg tasarla poster afiş duvar kağıdı galeri"),
    "command": ("komuta merkezi, çalışma modları, makrolar, modül aç/kapat", "mod modu sessiz araştırma mühendislik komuta acil makro kısayol senaryo modül komuta merkezi master control kontrol paneli"),
    "world": ("sanal dünya / şehir kurucu ve fizik hesapları", "şehir sanal dünya kasaba bina inşa trafik gece gündüz yerçekimi fizik düşme fren mesafe atış simülasyon yağmur kar sis rüzgar ateş yangın"),
    "knowledge": ("bilgi merkezi: belge kütüphanesi, kaynaklı cevap, özet, bilgi grafiği, sesli kitap, quiz, öğrenme planı", "kütüphane belge kitap pdf makale kaynak özetle grafik ilişki kavram sesli kitap quiz sınav test soru öğren öğrenme ders çalış tekrar kart plan epub"),
    "nodes": ("çoklu bilgisayar: diğer JARVIS'leri bağla, durum, uzaktan komut, dosya gönder/al, kuyruk", "bilgisayar bilgisayara bilgisayarda pc laptop dizüstü masaüstü düğüm ağdaki diğer uzak uzaktaki gönder oradaki ofisteki evdeki tüm bilgisayarlar"),
    "twin": ("dijital ikiz (bilgisayar/ev 3D canlı), protein yapıları, hücre modeli", "vr ar sanal gerçeklik artırılmış gözlük quest ikiz dijital ikiz protein enzim hemoglobin insülin pdb hücre organel mitokondri çekirdek bakteri biyoloji kasa donanım içini"),
    "music": ("müzik/ritim besteleme, MIDI", "müzik beste besteler şarkı melodi ritim davul beat lofi caz piyano ambient sinematik elektronik hiphop trap rock midi enstrümantal fon müziği"),
    "hud": ("büyük hava durumu paneli, AR masaüstü (elle yönetilen HUD panelleri, dairesel menü)", "hava havayı havada durumu tahmin yağmur sıcaklık derece masaüstü masaüstünü hud panel paneli dock menü"),
    "life": ("toplantı asistanı, odak/pomodoro, günlük, bitki doktoru, sulama, aydınlat beni haber sahneleri, AR oyunları", "toplantı toplantıyı toplantıya kayıt altyazı odak odaklan pomodoro çalışma günlük günlüğüme günlüğe nasıldım bitki bitkim bitkiyi çiçek sula suladım sulama yaprak aydınlat gündem haberleri oyun oyna taş kağıt makas balon"),
    "scene": ("odayı tara, nesne bul/nerede, belge tara, QR, renk, egzersiz sayacı, duruş, ruh hali, avuç HUD, havaya çizim, kask", "not bırak buzdolabına kapıya tara taraması odayı oda nesne nesneleri nerede bul bıraktım hologram belge belgeyi fatura yazıyı qr barkod karekod renk squat şınav zıplama egzersiz spor say tekrar duruş oturuş göz mola molası ruh duygu modum avuç avucumda çiz çizim çizdim maske kask hud"),
    "cams": ("telefon kameraları (JARVIS'in gözü), güvenlik modu", "kamera kameraya kameradan mutfak mutfakta salon salonda kapı kapıya bahçe oda odada bak göz izle güvenlik hareket alarm bebek ne var"),
    "library": ("kitaplık: kitaplarım, raf taraması, notlar, alıntılar, okuma durumu", "kitap kitabı kitaplık kitaplığım kitaplığımı raf raftan okudum okuyorum okunacak sayfa sayfadayım alıntı roman yazar bitirdim öner"),
    "arfx": ("kamera AR el efektleri, gezegen, kahve falı, uyku modu", "el efekt efektleri gezegen mars jüpiter satürn güneş ateş şimşek mühür büyü sihir hologram fal falıma falımı kahve fincan uyku uyu uyut alkış"),
    "browser": ("tarayıcı otomasyonu: siteye git, oku, tıkla, form doldur, sekmeler", "tarayıcı tarayıcıda site sitesine sitesinde sayfa sayfada form doldur tıkla sekme sekmeyi giriş yap rezervasyon bilet uçak otel sepet ürün sipariş edge chrome web"),
    "plugins": ("eklentiler", ""),
}


def _norm(t):
    return t.lower().replace("İ", "i").replace("I", "ı")


def pick_groups(text):
    words = re.findall(r"[\wçğıöşü-]+", _norm(text))
    out = {"core"}
    for g, (_, kws) in GROUP_INFO.items():
        for k in kws.split():
            if any((w.startswith(k) if len(k) >= 3 else w == k) for w in words):
                out.add(g)
                break
    out.add("plugins")
    out.add("semantic")
    return out


def enable_tools(groups):
    return "Etkinleştirildi: " + str(groups) + ". Artık bu araçları kullanabilirsin."


def specs(groups=None):
    out = []
    for n, t in TOOLS.items():
        if groups is None or TOOL_GROUP.get(n, "core") in groups or n == "enable_tools":
            out.append({"type": "function", "function": {"name": n, **t[1]}})
    return out


def reload_plugins():
    """plugins/ klasörünü yeniden yükler (JARVIS'i kapatmadan yeni yetenek)."""
    from .skills import load_plugins
    for n in [n for n, g in TOOL_GROUP.items() if g == "plugins"]:
        TOOLS.pop(n, None)
        TOOL_GROUP.pop(n, None)
    pt, pg = load_plugins()
    TOOLS.update(pt)
    TOOL_GROUP.update(pg)
    return len(pt)


TOOLS["enable_tools"] = (enable_tools, _schema(
    "Şu an elinde olmayan bir araç grubunu açar. Gruplar: " + "; ".join(f"{g} = {d}" for g, (d, _) in GROUP_INFO.items() if g != "plugins"),
    {"groups": S("virgülle grup adları")}, ["groups"]), False)
TOOL_GROUP["enable_tools"] = "core"


def is_critical(name, args):
    crit = TOOLS[name][2]
    return crit(args) if callable(crit) else bool(crit)


TOOL_TIMEOUT = {"web_search": 25, "news_search": 15, "read_webpage": 20, "weather": 15, "currency": 15,  # ağ araçları: süre sınırlı
                "browser_open": 45, "browser_read": 30, "browser_look": 45}


def _run_limited(fn, args, limit):
    """Aracı süre sınırıyla çalıştırır: takılan bir araç JARVIS'i dakikalarca bekletmesin."""
    import threading as _th
    box = {}

    def run():
        try:
            box["r"] = fn(**args)
        except BaseException as e:  # noqa: BLE001
            box["e"] = e
    t = _th.Thread(target=run, daemon=True)
    t.start()
    t.join(limit)
    if t.is_alive():
        raise TimeoutError()
    if "e" in box:
        raise box["e"]
    return box.get("r")


def execute(name, args):
    if name not in TOOLS:
        return f"Bilinmeyen araç: {name}"
    fn = TOOLS[name][0]
    try:
        result = _run_limited(fn, args or {}, TOOL_TIMEOUT[name]) if name in TOOL_TIMEOUT else fn(**(args or {}))
        ok = True
    except TimeoutError:
        result, ok = f"Araç {TOOL_TIMEOUT.get(name)} sn içinde bitmedi; başka bir yol dene.", False
    except TypeError as e:
        result, ok = f"Parametre hatası: {e}", False
    except Exception as e:
        result, ok = f"Hata: {type(e).__name__}: {e}", False
    memory.log_action(name, args, result, ok)
    if not isinstance(result, str):
        result = json.dumps(result, ensure_ascii=False, default=str)
    return result[:8000]
