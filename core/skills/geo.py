"""3D Dünya ve coğrafya: ülke bilgileri, karşılaştırma, konum bulma, mesafe, canlı uçuşlar, depremler,
deniz ticaret rotaları, tarihsel olay turu. Arayüzdeki 3D küreyi de bu araçlar yönetir (ui_* sonuçları)."""
import json
import math
import time
import urllib.parse

from ..config import WEB
from ..tools import N, S, _http_get, _schema

_countries = None
_cities = None


def _norm(s):
    return (s or "").lower().replace("İ", "i").replace("ı", "i").replace("ş", "s").replace("ğ", "g") \
        .replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("â", "a").strip()


def countries():
    global _countries
    if _countries is None:
        _countries = json.loads((WEB / "data" / "countries.json").read_text(encoding="utf-8"))
    return _countries


def cities():
    global _cities
    if _cities is None:
        _cities = json.loads((WEB / "data" / "cities.json").read_text(encoding="utf-8"))
    return _cities


ALIAS = {"abd": "united states of america", "amerika": "united states of america", "usa": "united states of america",
         "ingiltere": "united kingdom", "birlesik krallik": "united kingdom", "rusya": "russia", "cin": "china",
         "guney kore": "south korea", "kuzey kore": "north korea", "hollanda": "netherlands", "kktc": "n. cyprus",
         "kuzey kibris": "n. cyprus"}


def find_country(name):
    n = _norm(name)
    n = ALIAS.get(n, n)
    for c in countries():
        if n in (_norm(c["n"]), _norm(c["en"]), _norm(c["iso"])):
            return c
    for c in countries():
        if n and (n in _norm(c["n"]) or n in _norm(c["en"])):
            return c
    return None


def _capital(c):
    caps = [x for x in cities() if x["cap"] and _norm(x["c"]) == _norm(c["en"])]
    return caps[0] if caps else None


def _info(c):
    cap = _capital(c)
    return {"ülke": c["n"], "kıta": c["cont"], "bölge": c["sub"], "başkent": cap["n"] if cap else None,
            "nüfus": c["pop"], "nüfus_yılı": c["popy"], "yüzölçümü_km2": c["area"],
            "yoğunluk_kişi_km2": round(c["pop"] / c["area"], 1) if c["area"] else None,
            "gsyh_milyar_usd": round(c["gdp"] / 1000, 1), "gsyh_yılı": c["gdpy"],
            "kişi_başı_gsyh_usd": round(c["gdp"] * 1e6 / c["pop"]) if c["pop"] else None,
            "gelir_grubu": c["inc"], "ekonomi": c["eco"], "lat": c["ly"], "lon": c["lx"]}


def country_info(name):
    c = find_country(name)
    return _info(c) if c else f"'{name}' adlı ülke bulunamadı."


def compare_countries(names):
    out = []
    for n in str(names).split(","):
        c = find_country(n.strip())
        if c:
            i = _info(c)
            out.append({k: i[k] for k in ("ülke", "nüfus", "yüzölçümü_km2", "yoğunluk_kişi_km2", "gsyh_milyar_usd", "kişi_başı_gsyh_usd", "gelir_grubu")})
    return out or "Ülke bulunamadı."


def rank_countries(by="nüfus", top=10, continent=""):
    key = {"nüfus": "pop", "population": "pop", "yüzölçümü": "area", "alan": "area", "area": "area",
           "ekonomi": "gdp", "gsyh": "gdp", "gdp": "gdp", "kişi_başı": "pc", "yoğunluk": "dens"}.get(by, "pop")
    rows = []
    for c in countries():
        if continent and _norm(continent) not in _norm(c["cont"]) and _norm(continent) not in _norm(c["sub"]):
            continue
        v = {"pop": c["pop"], "area": c["area"], "gdp": c["gdp"], "pc": c["gdp"] * 1e6 / c["pop"] if c["pop"] else 0,
             "dens": c["pop"] / c["area"] if c["area"] else 0}[key]
        rows.append((v, c["n"]))
    rows.sort(reverse=True)
    return [{"sıra": i + 1, "ülke": n, "değer": round(v, 1)} for i, (v, n) in enumerate(rows[: int(top)])]


def geocode(place):
    c = find_country(place)
    if c:
        return {"ad": c["n"], "lat": c["ly"], "lon": c["lx"], "tür": "ülke", "zoom": 2.2}
    for x in cities():
        if _norm(x["n"]) == _norm(place):
            return {"ad": f"{x['n']}, {x['c']}", "lat": x["lat"], "lon": x["lon"], "tür": "şehir", "zoom": 1.45}
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": place, "format": "json", "limit": 1, "accept-language": "tr"})
    try:
        r = json.loads(_http_get(url))
    except Exception as e:
        raise RuntimeError(f"Konum aranamadı: {e}")
    if not r:
        raise RuntimeError(f"'{place}' bulunamadı.")
    r = r[0]
    kind = r.get("addresstype") or r.get("type", "")
    zoom = 1.45 if kind in ("city", "town", "state", "province") else 1.15
    return {"ad": r["display_name"][:120], "lat": float(r["lat"]), "lon": float(r["lon"]), "tür": kind, "zoom": zoom}


def haversine(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ---------- arayüz komutları: istemci bu araçların args/sonucunu görüp küreyi yönetir ----------
def globe_show(place=""):
    if not place:
        return {"ui": "globe", "mesaj": "3D Dünya açıldı."}
    g = geocode(place)
    c = find_country(place)
    return {"ui": "globe_fly", **g, **({"bilgi": _info(c)} if c else {})}


def globe_layer(layer, on=True):
    names = {"uçuş": "flights", "uçak": "flights", "flights": "flights", "deprem": "quakes", "quakes": "quakes",
             "gemi": "ships", "ships": "ships", "sınır": "borders", "borders": "borders", "şehir": "cities", "cities": "cities",
             "bulut": "clouds", "clouds": "clouds", "gece": "night", "night": "night", "hava": "weather"}
    w = _norm(layer).split()[0] if layer else ""
    lid = next((v for k, v in sorted(names.items(), key=lambda kv: -len(kv[0])) if w.startswith(_norm(k))), layer)
    return {"ui": "globe_layer", "layer": lid, "on": bool(on), "not": "gemi katmanı canlı değil: ana deniz ticaret rotaları" if lid == "ships" else ""}


def globe_mark(place, label=""):
    g = geocode(place)
    return {"ui": "globe_mark", **g, "label": label or g["ad"]}


def globe_distance(place_a, place_b):
    a, b = geocode(place_a), geocode(place_b)
    d = haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
    return {"ui": "globe_distance", "a": a, "b": b, "km": round(d, 1),
            "uçakla_saat": round(d / 850 + 0.5, 1), "not": "kuş uçuşu (büyük çember) mesafesi"}


def globe_street(place, satellite=True):
    g = geocode(place)
    return {"ui": "map", **g, "uydu": bool(satellite)}


def globe_story(title, events):
    """events: JSON [{"year": 1453, "place": "İstanbul", "text": "..."}]"""
    ev = json.loads(events) if isinstance(events, str) else events
    out = []
    for e in ev[:20]:
        try:
            g = geocode(e.get("place", "")) if "lat" not in e else {"lat": e["lat"], "lon": e["lon"], "ad": e.get("place", "")}
            out.append({"year": e.get("year"), "text": e.get("text", ""), "lat": g["lat"], "lon": g["lon"], "place": g["ad"]})
        except Exception:
            pass
        time.sleep(0.05)
    return {"ui": "globe_story", "title": title, "events": out}


# ---------- canlı veriler ----------
def flights(lamin=-90, lomin=-180, lamax=90, lomax=180, limit=2500):
    url = "https://opensky-network.org/api/states/all"
    if (lamin, lomin, lamax, lomax) != (-90, -180, 90, 180):
        url += "?" + urllib.parse.urlencode({"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax})
    d = json.loads(_http_get(url, timeout=20))
    out = []
    for s in d.get("states") or []:
        if s[5] is None or s[6] is None or s[8]:
            continue
        out.append({"cs": (s[1] or "").strip(), "ülke": s[2], "lon": round(s[5], 3), "lat": round(s[6], 3),
                    "alt": round((s[7] or s[13] or 0)), "hız_kmh": round((s[9] or 0) * 3.6), "yön": round(s[10] or 0)})
        if len(out) >= limit:
            break
    return out


def flights_near(place, radius_km=150):
    g = geocode(place)
    dlat = radius_km / 111
    dlon = radius_km / (111 * max(0.2, math.cos(math.radians(g["lat"]))))
    f = flights(g["lat"] - dlat, g["lon"] - dlon, g["lat"] + dlat, g["lon"] + dlon, 200)
    return {"ui": "globe_fly", "lat": g["lat"], "lon": g["lon"], "zoom": 1.5, "ad": g["ad"],
            "uçak_sayısı": len(f), "örnekler": f[:8], "katman": "flights"}


def earthquakes(period="day", min_mag=2.5):
    feed = {"hour": "all_hour", "day": "all_day", "week": "all_week"}.get(period, "all_day")
    d = json.loads(_http_get(f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson", timeout=20))
    out = []
    for f in d["features"]:
        m = f["properties"]["mag"] or 0
        if m < float(min_mag):
            continue
        lon, lat, depth = f["geometry"]["coordinates"]
        out.append({"büyüklük": m, "yer": f["properties"]["place"], "lat": lat, "lon": lon, "derinlik_km": depth,
                    "zaman": time.strftime("%d.%m %H:%M", time.localtime(f["properties"]["time"] / 1000))})
    out.sort(key=lambda x: -x["büyüklük"])
    return out


def earthquakes_tool(period="day", min_mag=4, region=""):
    q = earthquakes(period, min_mag)
    if region:
        q = [x for x in q if _norm(region) in _norm(x["yer"])] or q
    return {"ui": "globe_layer", "layer": "quakes", "on": True, "sayı": len(q), "en_büyükler": q[:10]}


SHIP_ROUTES = [  # ana deniz ticaret rotaları (yaklaşık ara noktalar)
    ("Asya-Avrupa (Süveyş)", [(31.2, 121.5), (22.3, 114.2), (1.3, 103.8), (6, 80), (12.5, 45), (30, 32.5), (36, 15), (36, -5.5), (51, 1.5), (51.9, 4.1)]),
    ("Trans-Pasifik", [(31.2, 121.5), (35, 140), (45, 180), (40, -140), (33.7, -118.3)]),
    ("Trans-Atlantik", [(51.9, 4.1), (49, -10), (42, -40), (40.6, -74)]),
    ("Panama", [(40.6, -74), (25, -77), (9.3, -79.9), (8.9, -79.5), (0, -85), (-12, -77.1)]),
    ("Ümit Burnu", [(1.3, 103.8), (-10, 80), (-34.4, 18.5), (-10, 0), (6.4, 3.4)]),
    ("Karadeniz-Akdeniz", [(46.5, 30.7), (41.2, 29.1), (40.0, 26.2), (37, 25), (35, 20)]),
    ("Basra Körfezi", [(26.2, 50.6), (26.5, 56.3), (20, 63), (12.5, 45)]),
]


def ships():
    return [{"ad": n, "nokta": pts} for n, pts in SHIP_ROUTES]


TOOLS = {
    "globe_show": (globe_show, _schema("3D Dünya küresini açar ve bir ülke/şehir/adrese uçar (boş: sadece küreyi açar).", {"place": S("yer")}), False),
    "globe_layer": (globe_layer, _schema("Kürede katman açar/kapatır: flights (canlı uçuşlar), quakes (depremler), ships (deniz rotaları), borders, cities, clouds, night.",
                                         {"layer": S("katman"), "on": {"type": "boolean"}}, ["layer"]), False),
    "globe_mark": (globe_mark, _schema("Kürede bir konumu işaretler.", {"place": S("yer"), "label": S("etiket")}, ["place"]), False),
    "globe_distance": (globe_distance, _schema("İki yer arası kuş uçuşu mesafe; kürede yay çizer.", {"place_a": S("A"), "place_b": S("B")}, ["place_a", "place_b"]), False),
    "globe_street": (globe_street, _schema("Bir yeri sokak seviyesinde harita veya uydu görüntüsüyle açar.",
                                           {"place": S("yer/adres"), "satellite": {"type": "boolean"}}, ["place"]), False),
    "globe_story": (globe_story, _schema("Tarihsel olayları kürede sırayla canlandırır (3D tarih turu). Olayları sen hazırla.",
                                         {"title": S("başlık"), "events": S('JSON [{"year":1453,"place":"İstanbul","text":"..."}]')}, ["title", "events"]), False),
    "country_info": (country_info, _schema("Ülke bilgisi: nüfus, yüzölçümü, yoğunluk, GSYH, kişi başı gelir, başkent.", {"name": S("ülke")}, ["name"]), False),
    "compare_countries": (compare_countries, _schema("Ülkeleri nüfus/alan/ekonomi bakımından karşılaştırır.", {"names": S("virgülle ülkeler")}, ["names"]), False),
    "rank_countries": (rank_countries, _schema("Ülke sıralaması (nüfus, yüzölçümü, gsyh, kişi_başı, yoğunluk).",
                                               {"by": S("ölçüt"), "top": N("kaç"), "continent": S("kıta (isteğe bağlı, İngilizce: Europe, Asia...)")}), False),
    "flights_near": (flights_near, _schema("Bir yerin çevresindeki canlı uçuşlar.", {"place": S("yer"), "radius_km": N("yarıçap")}, ["place"]), False),
    "earthquakes": (earthquakes_tool, _schema("Son depremler (USGS) ve küre katmanı.",
                                              {"period": {"type": "string", "enum": ["hour", "day", "week"]}, "min_mag": N("en az büyüklük"), "region": S("bölge")}), False),
}
