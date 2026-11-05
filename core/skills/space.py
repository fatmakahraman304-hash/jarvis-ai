"""Uzay merkezi: gerçek gezegen konumları (JPL yaklaşık Kepler elemanları, 1800–2050), Ay konumu ve evresi,
bir yerden 'bu gece gökyüzü' (yükseklik/yön), uydular ve ISS (CelesTrak yörünge verisi, J2 düzeltmeli Kepler yayılımı),
uzay araçları (NASA JPL Horizons), arayüzdeki 3D uzay sahnesini yöneten araçlar."""
import datetime as dt
import json
import math
import re
import time
import urllib.parse

from ..config import WEB
from ..tools import N, S, _http_get, _schema

DEG = math.pi / 180
AU_KM = 149597870.7
OBLIQ = 23.43928 * DEG

# JPL "Keplerian Elements for Approximate Positions of the Major Planets", Tablo 1 (1800–2050)
# a(AU), e, I, L, uzun.perihel, uzun.düğüm  ve yüzyıllık değişimleri
PLANETS = {
    "Merkür": ([0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593],
               [0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081]),
    "Venüs": ([0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255],
              [0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418]),
    "Dünya": ([1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0],
              [0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0]),
    "Mars": ([1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891],
             [0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343]),
    "Jüpiter": ([5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909],
                [-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106]),
    "Satürn": ([9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448],
               [-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794]),
    "Uranüs": ([19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503],
               [-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589]),
    "Neptün": ([30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574],
               [0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664]),
}
INFO = {"Merkür": (4879, 0, "58,6 gün"), "Venüs": (12104, 0, "243 gün (ters)"), "Dünya": (12742, 1, "24 saat"),
        "Mars": (6779, 2, "24,6 saat"), "Jüpiter": (139820, 95, "9,9 saat"), "Satürn": (116460, 146, "10,7 saat"),
        "Uranüs": (50724, 28, "17,2 saat"), "Neptün": (49244, 16, "16,1 saat")}


def jd(t=None):
    t = t or dt.datetime.now(dt.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp() / 86400 + 2440587.5


def _kepler(M, e):
    E = M + e * math.sin(M)
    for _ in range(12):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    return E


def helio(name, JD):
    """Güneş merkezli ekliptik koordinat (AU)."""
    el, rt = PLANETS[name]
    T = (JD - 2451545.0) / 36525
    a, e, I, L, wbar, Om = [el[i] + rt[i] * T for i in range(6)]
    I, Om, wbar = I * DEG, Om * DEG, wbar * DEG
    M = ((L * DEG - wbar) + math.pi) % (2 * math.pi) - math.pi
    w = wbar - Om
    E = _kepler(M, e)
    xp, yp = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    cw, sw, cO, sO, cI, sI = math.cos(w), math.sin(w), math.cos(Om), math.sin(Om), math.cos(I), math.sin(I)
    x = (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp
    y = (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp
    z = (sw * sI) * xp + (cw * sI) * yp
    return x, y, z


def ecl2eq(x, y, z):
    return x, y * math.cos(OBLIQ) - z * math.sin(OBLIQ), y * math.sin(OBLIQ) + z * math.cos(OBLIQ)


def radec(x, y, z):
    ra = math.atan2(y, x) / DEG % 360
    dec = math.atan2(z, math.hypot(x, y)) / DEG
    return ra, dec


def moon(JD):
    """Ay: düşük hassasiyetli kuram (~0,5°). Dönüş: ekliptik boylam/enlem (°), uzaklık (km)."""
    d = JD - 2451545.0
    L = (218.316 + 13.176396 * d) % 360
    M = (134.963 + 13.064993 * d) % 360
    F = (93.272 + 13.229350 * d) % 360
    D = (297.850 + 12.190749 * d) % 360
    Ms = (357.529 + 0.98560028 * d) % 360
    lam = L + 6.289 * math.sin(M * DEG) + 1.274 * math.sin((2 * D - M) * DEG) + 0.658 * math.sin(2 * D * DEG) - 0.186 * math.sin(Ms * DEG)
    beta = 5.128 * math.sin(F * DEG)
    dist = 385001 - 20905 * math.cos(M * DEG)
    return lam % 360, beta, dist


def geo_radec(name, JD):
    if name == "Ay":
        lam, beta, dist = moon(JD)
        x = math.cos(beta * DEG) * math.cos(lam * DEG)
        y = math.cos(beta * DEG) * math.sin(lam * DEG)
        z = math.sin(beta * DEG)
        ra, dec = radec(*ecl2eq(x, y, z))
        return ra, dec, dist / AU_KM
    ex, ey, ez = helio("Dünya", JD)
    if name == "Güneş":
        x, y, z = -ex, -ey, -ez
    else:
        px, py, pz = helio(name, JD)
        x, y, z = px - ex, py - ey, pz - ez
    ra, dec = radec(*ecl2eq(x, y, z))
    return ra, dec, math.sqrt(x * x + y * y + z * z)


def gmst(JD):
    return (280.46061837 + 360.98564736629 * (JD - 2451545.0)) % 360


def altaz(ra, dec, lat, lon, JD):
    H = (gmst(JD) + lon - ra) * DEG
    la, de = lat * DEG, dec * DEG
    alt = math.asin(math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(H))
    az = math.atan2(-math.sin(H) * math.cos(de), math.cos(la) * math.sin(de) - math.sin(la) * math.cos(de) * math.cos(H))
    return alt / DEG, az / DEG % 360


def direction(az):
    return ["Kuzey", "Kuzeydoğu", "Doğu", "Güneydoğu", "Güney", "Güneybatı", "Batı", "Kuzeybatı"][int((az + 22.5) // 45) % 8]


def moon_phase(JD):
    lam, _, _ = moon(JD)
    ex, ey, _ = helio("Dünya", JD)
    sun_lon = math.atan2(-ey, -ex) / DEG % 360
    elong = (lam - sun_lon) % 360
    illum = (1 - math.cos(elong * DEG)) / 2
    names = ["Yeni Ay", "Hilal (büyüyen)", "İlk dördün", "Şişkin (büyüyen)", "Dolunay", "Şişkin (küçülen)", "Son dördün", "Hilal (küçülen)"]
    return {"evre": names[int((elong + 22.5) // 45) % 8], "aydınlık_%": round(illum * 100), "elongasyon": round(elong, 1)}


def _parse_when(when):
    if not when:
        return dt.datetime.now(dt.timezone.utc)
    s = str(when).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(s, fmt).astimezone(dt.timezone.utc)
        except ValueError:
            pass
    return dt.datetime.now(dt.timezone.utc)


# ===================== araçlar =====================
def planet_positions(date=""):
    t = _parse_when(date)
    J = jd(t)
    ex, ey, ez = helio("Dünya", J)
    out = []
    for n in PLANETS:
        x, y, z = helio(n, J)
        r = math.sqrt(x * x + y * y + z * z)
        d = math.sqrt((x - ex) ** 2 + (y - ey) ** 2 + (z - ez) ** 2)
        out.append({"gezegen": n, "güneşe_au": round(r, 3), "dünyaya_milyon_km": None if n == "Dünya" else round(d * AU_KM / 1e6, 1),
                    "ışık_süresi_dk": None if n == "Dünya" else round(d * AU_KM / 299792.458 / 60, 1),
                    "ekliptik_boylam": round(math.atan2(y, x) / DEG % 360, 1)})
    return {"tarih_utc": t.strftime("%Y-%m-%d %H:%M"), "gezegenler": out, "ay": moon_phase(J)}


def sky_tonight(place="Istanbul", time_local=""):
    """Bir yerden gökyüzünde şu an (veya verilen saatte) görünen gezegenler, Ay ve parlak yıldızlar."""
    from .geo import geocode
    g = geocode(place)
    t = _parse_when(time_local)
    J = jd(t)
    vis = []
    for n in ["Ay", "Merkür", "Venüs", "Mars", "Jüpiter", "Satürn", "Uranüs", "Neptün", "Güneş"]:
        ra, dec, dist = geo_radec(n, J)
        alt, az = altaz(ra, dec, g["lat"], g["lon"], J)
        if alt > 0:
            vis.append({"gök_cismi": n, "yükseklik": round(alt, 1), "yön": direction(az), "azimut": round(az)})
    sun_alt = altaz(*geo_radec("Güneş", J)[:2], g["lat"], g["lon"], J)[0]
    stars = json.loads((WEB / "data" / "stars.json").read_text(encoding="utf-8"))
    bright = []
    for ra, dec, mag, bv, name, con in stars:
        if name and mag < 1.6:
            alt, az = altaz(ra % 360, dec, g["lat"], g["lon"], J)
            if alt > 10:
                bright.append({"yıldız": name, "parlaklık_kadir": mag, "yükseklik": round(alt, 1), "yön": direction(az)})
    bright.sort(key=lambda s: s["parlaklık_kadir"])
    return {"ui": "space", "view": "sky", "lat": g["lat"], "lon": g["lon"], "yer": g["ad"], "zaman_utc": t.strftime("%Y-%m-%d %H:%M"),
            "güneş_yüksekliği": round(sun_alt, 1), "gökyüzü": "karanlık (gözlem için iyi)" if sun_alt < -12 else "alacakaranlık" if sun_alt < 0 else "gündüz",
            "görünenler": [v for v in vis if v["gök_cismi"] != "Güneş"], "parlak_yıldızlar": bright[:10], "ay": moon_phase(J)}


# ---------- uydular ----------
MU, RE, J2 = 398600.4418, 6378.137, 1.08262668e-3
_sat_cache = {}
GROUPS = {"stations": "stations", "istasyon": "stations", "visual": "visual", "parlak": "visual", "gps": "gps-ops",
          "hava": "weather", "weather": "weather", "starlink": "starlink", "geo": "geo", "bilim": "science", "science": "science",
          "aktif": "active", "active": "active", "türk": "active"}


def sat_elements(group="stations"):
    grp = GROUPS.get(group.lower(), group)
    c = _sat_cache.get(grp)
    if c and time.time() - c[0] < 7200:
        return c[1]
    data = json.loads(_http_get(f"https://celestrak.org/NORAD/elements/gp.php?GROUP={urllib.parse.quote(grp)}&FORMAT=json", timeout=30))
    els = [{"ad": s["OBJECT_NAME"], "id": s["NORAD_CAT_ID"], "epoch": s["EPOCH"], "n": s["MEAN_MOTION"], "e": s["ECCENTRICITY"],
            "i": s["INCLINATION"], "raan": s["RA_OF_ASC_NODE"], "argp": s["ARG_OF_PERICENTER"], "M": s["MEAN_ANOMALY"]} for s in data]
    _sat_cache[grp] = (time.time(), els)
    return els


def sat_position(el, t=None):
    """J2 seküler düzeltmeli Kepler yayılımı (görselleştirme için; SGP4 değil, birkaç gün içinde ~10 km mertebesinde)."""
    t = t or dt.datetime.now(dt.timezone.utc)
    ep = dt.datetime.fromisoformat(el["epoch"].replace("Z", "")).replace(tzinfo=dt.timezone.utc)
    dts = (t - ep).total_seconds()
    n = el["n"] * 2 * math.pi / 86400
    a = (MU / n ** 2) ** (1 / 3)
    e, i = el["e"], el["i"] * DEG
    p = a * (1 - e * e)
    k = 1.5 * n * J2 * (RE / p) ** 2
    raan = el["raan"] * DEG - k * math.cos(i) * dts
    argp = el["argp"] * DEG + 0.5 * k * (5 * math.cos(i) ** 2 - 1) * dts
    M = el["M"] * DEG + n * dts
    E = _kepler(M % (2 * math.pi), e)
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2), math.sqrt(1 - e) * math.cos(E / 2))
    r = a * (1 - e * math.cos(E))
    u = argp + nu
    x = r * (math.cos(raan) * math.cos(u) - math.sin(raan) * math.sin(u) * math.cos(i))
    y = r * (math.sin(raan) * math.cos(u) + math.cos(raan) * math.sin(u) * math.cos(i))
    z = r * math.sin(u) * math.sin(i)
    th = gmst(jd(t)) * DEG
    xe, ye = x * math.cos(th) + y * math.sin(th), -x * math.sin(th) + y * math.cos(th)
    lat = math.atan2(z, math.hypot(xe, ye)) / DEG
    lon = (math.atan2(ye, xe) / DEG + 540) % 360 - 180
    return {"lat": round(lat, 3), "lon": round(lon, 3), "yükseklik_km": round(r - RE), "hız_kmh": round(math.sqrt(MU * (2 / r - 1 / a)) * 3600)}


def satellite_where(name="ISS", group="stations"):
    els = sat_elements(group)
    q = name.lower().replace("iss", "iss (zarya)")
    el = next((x for x in els if x["ad"].lower() == q), None) or next((x for x in els if name.lower() in x["ad"].lower()), None)
    if not el:
        return f"'{name}' bulunamadı ({group} grubunda)."
    pos = sat_position(el)
    try:
        over = _country_at(pos["lat"], pos["lon"]) or "okyanus / deniz"
    except Exception:
        over = "bilinmiyor"
    return {"ui": "space", "view": "satellites", "group": group, "focus": el["ad"], "uydu": el["ad"], "norad": el["id"], **pos, "üzerinde": over,
            "periyot_dk": round(1440 / el["n"], 1), "veri_tarihi": el["epoch"][:16]}


def _country_at(lat, lon):
    from .geo import countries

    def inring(x, y, ring):
        ins = False
        for k in range(len(ring)):
            xi, yi = ring[k]
            xj, yj = ring[k - 1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                ins = not ins
        return ins
    for c in countries():
        for poly in c["poly"]:
            if inring(lon, lat, poly[0]):
                return c["n"]
    return None


def satellites_overview(group="stations"):
    els = sat_elements(group)
    return {"ui": "space", "view": "satellites", "group": group, "sayı": len(els), "örnekler": [e["ad"] for e in els[:15]]}


# ---------- uzay araçları ----------
CRAFT = {"Voyager 1": "-31", "Voyager 2": "-32", "New Horizons": "-98", "Parker Solar Probe": "-96", "James Webb": "-170",
         "Juno": "-61", "Europa Clipper": "-159", "Lucy": "-49", "Psyche": "-255", "Solar Orbiter": "-144"}
_craft_cache = {}


def spacecraft_positions():
    if _craft_cache.get("t") and time.time() - _craft_cache["t"] < 6 * 3600:
        return _craft_cache["v"]
    now = dt.datetime.now(dt.timezone.utc)
    start, stop = now.strftime("%Y-%m-%d"), (now + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    J = jd(now)
    ex, ey, ez = helio("Dünya", J)
    out = []
    for name, cid in CRAFT.items():
        q = {"format": "json", "COMMAND": f"'{cid}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'VECTORS'",
             "CENTER": "'500@10'", "REF_PLANE": "'ECLIPTIC'", "OUT_UNITS": "'AU-D'", "VEC_TABLE": "'1'",
             "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": "'1 d'"}
        try:
            res = json.loads(_http_get("https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(q), timeout=25)).get("result", "")
            blk = res.split("$$SOE")[1].split("$$EOE")[0]
            x, y, z = (float(v) for v in re.findall(r"[XYZ] =\s*([-+0-9.E]+)", blk)[:3])
            r = math.sqrt(x * x + y * y + z * z)
            de = math.sqrt((x - ex) ** 2 + (y - ey) ** 2 + (z - ez) ** 2)
            out.append({"ad": name, "x": x, "y": y, "z": z, "güneşe_au": round(r, 2), "dünyaya_au": round(de, 2),
                        "ışık_süresi_saat": round(de * AU_KM / 299792.458 / 3600, 2)})
        except Exception:
            continue
    _craft_cache.update(t=time.time(), v=out)
    return out


def space_show(view="system", params="{}"):
    """view: system (canlı güneş sistemi), satellites, sky (gökyüzü), moon, mars, planet, blackhole, galaxy, universe"""
    tr = {"güneş sistemi": "system", "sistem": "system", "uydular": "satellites", "uydu": "satellites", "yıldızlar": "sky", "gökyüzü": "sky",
          "ay": "moon", "mars": "mars", "kara delik": "blackhole", "galaksi": "galaxy", "evren": "universe", "gezegen": "planet"}
    v = tr.get(view.lower(), view.lower())
    try:
        p = json.loads(params) if isinstance(params, str) else (params or {})
    except Exception:
        p = {}
    return {"ui": "space", "view": v, **p}


def spacecraft_tool():
    c = spacecraft_positions()
    return {"ui": "space", "view": "system", "craft": True, "araçlar": [{k: v for k, v in x.items() if k not in "xyz"} for x in c]}


TOOLS = {
    "space_show": (space_show, _schema("Uzay sahnesini açar: system (canlı güneş sistemi, gerçek konumlar), satellites (uydular), sky (yıldız haritası), moon (Ay yüzeyi), "
                                       "mars (Mars yüzeyi), planet ({\"name\":\"Jüpiter\"}), blackhole (kara delik simülasyonu), galaxy (kendi galaksin: {\"arms\":3,\"stars\":80000,\"spin\":1.2,\"inner\":\"#ffcc88\",\"outer\":\"#5599ff\"}), universe (kozmik ağ).",
                                       {"view": S("sahne"), "params": S("JSON parametre")}, ["view"]), False),
    "planet_positions": (planet_positions, _schema("Gezegenlerin gerçek konumları, Dünya'ya uzaklıkları, ışık süreleri ve Ay evresi (istenen tarihte).", {"date": S("YYYY-AA-GG (boş: şimdi)")}), False),
    "sky_tonight": (sky_tonight, _schema("Bir yerden gökyüzünde şu an (veya verilen saatte) görünen gezegenler, Ay ve parlak yıldızlar; yön ve yükseklikleriyle.",
                                         {"place": S("şehir"), "time_local": S("YYYY-AA-GG SS:DD (UTC; boş: şimdi)")}), False),
    "satellite_where": (satellite_where, _schema("Bir uydunun (ISS, Hubble, Türksat...) şu anki konumu, yüksekliği, hızı ve üzerinden geçtiği ülke; 3D'de gösterir.",
                                                 {"name": S("uydu adı"), "group": S("stations, visual, gps, weather, starlink, geo, science, active")}), False),
    "satellites_overview": (satellites_overview, _schema("Bir uydu grubunu canlı yörüngeleriyle 3D'de gösterir.", {"group": S("grup")}), False),
    "spacecraft_positions": (spacecraft_tool, _schema("Voyager, New Horizons, James Webb, Parker, Juno gibi uzay araçlarının NASA JPL'den gerçek konumları."), False),
}
