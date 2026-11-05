"""HUD verisi: büyük hava durumu paneli (Open-Meteo, ücretsiz, anahtarsız), AR masaüstü panelleri için sistem / haber / işler.
'hava durumunu göster' → tam ekran hava paneli (anlık, yüksek/düşük, yağmur, UV, gün doğumu/batımı, saatlik eğri, 7 gün)."""
import json
import time
import urllib.parse
import urllib.request

from ..config import load_settings
from ..tools import S, _schema

_cache = {}
WMO = {0: ("Açık", "sun"), 1: ("Çoğunlukla açık", "sun"), 2: ("Parçalı bulutlu", "partly"), 3: ("Kapalı", "cloud"), 45: ("Sisli", "fog"), 48: ("Kırağılı sis", "fog"),
       51: ("Hafif çisenti", "drizzle"), 53: ("Çisenti", "drizzle"), 55: ("Yoğun çisenti", "drizzle"), 61: ("Hafif yağmur", "rain"), 63: ("Yağmurlu", "rain"),
       65: ("Şiddetli yağmur", "rain"), 66: ("Dondurucu yağmur", "rain"), 67: ("Dondurucu yağmur", "rain"), 71: ("Hafif kar", "snow"), 73: ("Karlı", "snow"),
       75: ("Yoğun kar", "snow"), 77: ("Kar taneleri", "snow"), 80: ("Sağanak", "rain"), 81: ("Sağanak", "rain"), 82: ("Şiddetli sağanak", "storm"),
       85: ("Kar sağanağı", "snow"), 86: ("Kar sağanağı", "snow"), 95: ("Gök gürültülü", "storm"), 96: ("Dolu ile fırtına", "storm"), 99: ("Dolu ile fırtına", "storm")}
DAYS = ["PZT", "SAL", "ÇAR", "PER", "CUM", "CMT", "PAZ"]


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-HUD"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _geo(city):
    k = ("geo", city.lower())
    if k in _cache:
        return _cache[k]
    d = _get("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({"name": city, "count": 1, "language": "tr", "format": "json"}))
    r = (d.get("results") or [None])[0]
    if not r:
        raise RuntimeError(f"'{city}' bulunamadı")
    v = {"ad": r.get("name", city), "ülke": r.get("country", ""), "bölge": r.get("admin1", ""), "lat": r["latitude"], "lon": r["longitude"]}
    _cache[k] = v
    return v


def weather_full(city=""):
    city = (city or load_settings().get("city") or "Istanbul").strip()
    k = ("wx", city.lower())
    if k in _cache and time.time() - _cache[k][0] < 600:
        return _cache[k][1]
    g = _geo(city)
    q = {"latitude": g["lat"], "longitude": g["lon"], "timezone": "auto", "forecast_days": 7,
         "current": "temperature_2m,apparent_temperature,weather_code,relative_humidity_2m,wind_speed_10m,is_day",
         "hourly": "temperature_2m,precipitation_probability,weather_code",
         "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset,uv_index_max"}
    d = _get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q))
    cur, dl, hr = d.get("current", {}), d.get("daily", {}), d.get("hourly", {})
    now_iso = cur.get("time", "")[:13]
    times = hr.get("time", [])
    i0 = next((i for i, t in enumerate(times) if t[:13] >= now_iso), 0)
    hourly = [{"saat": times[i][11:16], "derece": round(hr["temperature_2m"][i]), "yağmur": hr["precipitation_probability"][i] or 0,
               "ikon": WMO.get(hr["weather_code"][i], ("", "cloud"))[1]} for i in range(i0, min(len(times), i0 + 24))]
    days = []
    for i, day in enumerate(dl.get("time", [])):
        wd = time.strptime(day, "%Y-%m-%d").tm_wday
        days.append({"gün": "BUGÜN" if i == 0 else DAYS[wd], "tarih": day[8:10] + "." + day[5:7], "max": round(dl["temperature_2m_max"][i]), "min": round(dl["temperature_2m_min"][i]),
                     "yağmur": dl["precipitation_probability_max"][i] or 0, "durum": WMO.get(dl["weather_code"][i], ("?", "cloud"))[0], "ikon": WMO.get(dl["weather_code"][i], ("", "cloud"))[1]})
    code = cur.get("weather_code", 0)
    out = {"şehir": g["ad"], "ülke": g["ülke"], "bölge": g["bölge"], "saat": cur.get("time", "").replace("T", " "),
           "derece": round(cur.get("temperature_2m", 0)), "hissedilen": round(cur.get("apparent_temperature", 0)), "nem": cur.get("relative_humidity_2m"),
           "rüzgar": round(cur.get("wind_speed_10m", 0)), "durum": WMO.get(code, ("?", "cloud"))[0], "ikon": WMO.get(code, ("", "cloud"))[1], "gündüz": bool(cur.get("is_day", 1)),
           "yüksek": days[0]["max"] if days else None, "düşük": days[0]["min"] if days else None, "yağmur": days[0]["yağmur"] if days else None,
           "uv": round(dl.get("uv_index_max", [0])[0] or 0) if dl.get("uv_index_max") else None,
           "doğuş": (dl.get("sunrise") or [""])[0][11:16], "batış": (dl.get("sunset") or [""])[0][11:16], "saatlik": hourly, "günler": days, "kaynak": "Open-Meteo"}
    _cache[k] = (time.time(), out)
    return out


def weather_panel(city=""):
    """Büyük hava durumu panelini açar (ekranda) ve kısa özet döner."""
    try:
        w = weather_full(city)
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"
    return {"ui": "weather", "data": w, "özet": f"{w['şehir']}: {w['derece']}°, {w['durum']}, hissedilen {w['hissedilen']}°, en yüksek {w['yüksek']}°, en düşük {w['düşük']}°, yağmur ihtimali %{w['yağmur']}.",
            "not": "Panel ekranda açıldı; özeti bir iki cümleyle söyle."}


def system_full():
    import psutil
    out = {"cpu": psutil.cpu_percent(interval=0.2), "ram": psutil.virtual_memory().percent}
    try:
        import os
        out["disk"] = psutil.disk_usage("C:\\" if os.name == "nt" else "/").percent
    except Exception:
        pass
    try:
        from .twin import _gpu
        g = _gpu()
        if isinstance(g, dict) and g.get("kullanım") is not None:
            out["gpu"] = g.get("kullanım")
        elif isinstance(g, list) and g and isinstance(g[0], dict):
            out["gpu"] = g[0].get("kullanım") or g[0].get("yük")
    except Exception:
        pass
    return out


def news_top(n=6):
    k = ("news",)
    if k in _cache and time.time() - _cache[k][0] < 600:
        return _cache[k][1]
    from .daily import news
    items = news("", limit=n)
    items = items if isinstance(items, list) else []
    _cache[k] = (time.time(), items)
    return items


def tasks_top():
    from .automation import todo_list
    t = todo_list()
    return t if isinstance(t, list) else []


def ar_desktop(panel=""):
    return {"ui": "handfx", "action": "desktop", "panel": panel,
            "not": "AR masaüstü: alttaki dock'tan ya da avucunu açıp tutunca çıkan dairesel menüden panel seç; paneli çimdikle tutup taşı, iki elle büyüt, ✕ ile kapat."}


GROUP = "hud"
TOOLS = {
    "weather_panel": (weather_panel, _schema("Büyük HAVA DURUMU panelini ekranda açar: anlık, yüksek/düşük, yağmur, UV, gün doğumu/batımı, saatlik eğri, 7 günlük tahmin.",
                                             {"city": S("şehir (boşsa ayarlardaki)")}), False),
    "ar_desktop": (ar_desktop, _schema("AR masaüstü: kamerada elle yönetilen HUD panelleri (saat, sistem, hava, haberler, işler, müzik, dünya) ve dairesel menü.",
                                       {"panel": S("açılacak panel: clock | system | weather | news | tasks | music | globe")}), False),
}
