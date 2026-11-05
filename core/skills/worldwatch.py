"""Canlı dünya takibi: NASA EONET doğal olaylar (yangın, fırtına, sel, volkan, toz, buz), NASA FIRMS yangın noktaları (anahtar ile),
NASA GIBS günlük uydu görüntüsü, RainViewer yağış radarı, haritada uluslararası haberler, AIS canlı gemi trafiği (aisstream.io anahtarı ile)."""
import base64
import json
import os
import socket
import ssl
import struct
import threading
import time
import urllib.parse

from ..config import DATA, env
from ..tools import N, S, _http_get, _schema

CAT_TR = {"wildfires": "Orman yangını", "severeStorms": "Şiddetli fırtına", "floods": "Sel", "volcanoes": "Volkan", "earthquakes": "Deprem",
          "seaLakeIce": "Deniz/göl buzu", "dustHaze": "Toz / pus", "landslides": "Heyelan", "drought": "Kuraklık", "snow": "Kar",
          "tempExtremes": "Aşırı sıcaklık", "manmade": "İnsan kaynaklı", "waterColor": "Su rengi"}
_cache = {}


def _cached(key, ttl, fn):
    c = _cache.get(key)
    if c and time.time() - c[0] < ttl:
        return c[1]
    v = fn()
    _cache[key] = (time.time(), v)
    return v


def eonet(days=30, category=""):
    def load():
        q = {"status": "open", "days": int(days)}
        if category:
            q["category"] = category
        d = json.loads(_http_get("https://eonet.gsfc.nasa.gov/api/v3/events?" + urllib.parse.urlencode(q), timeout=30))
        out = []
        for e in d.get("events", []):
            cat = (e.get("categories") or [{}])[0].get("id", "")
            geo = e.get("geometry") or []
            track = []
            for g in geo:
                c = g.get("coordinates")
                if g.get("type") == "Point" and c:
                    track.append([round(c[1], 3), round(c[0], 3), g.get("date", "")[:16], g.get("magnitudeValue"), g.get("magnitudeUnit")])
                elif g.get("type") == "Polygon" and c:
                    ring = c[0]
                    track.append([round(sum(p[1] for p in ring) / len(ring), 3), round(sum(p[0] for p in ring) / len(ring), 3), g.get("date", "")[:16], None, None])
            if track:
                out.append({"ad": e.get("title"), "tür": cat, "tür_tr": CAT_TR.get(cat, cat), "son": track[-1], "iz": track[-40:],
                            "kaynak": (e.get("sources") or [{}])[0].get("url", "")})
        return out
    return _cached(f"eonet{days}{category}", 1800, load)


def world_events(category="", days=30):
    tr = {"yangın": "wildfires", "fırtına": "severeStorms", "kasırga": "severeStorms", "tayfun": "severeStorms", "sel": "floods",
          "volkan": "volcanoes", "yanardağ": "volcanoes", "toz": "dustHaze", "heyelan": "landslides", "buz": "seaLakeIce", "kar": "snow"}
    cat = next((v for k, v in tr.items() if category and category.lower().startswith(k)), category)
    ev = eonet(days, cat if cat in CAT_TR else "")
    counts = {}
    for e in ev:
        counts[e["tür_tr"]] = counts.get(e["tür_tr"], 0) + 1
    return {"ui": "globe_layer", "layer": "events", "on": True, "category": cat if cat in CAT_TR else "", "toplam": len(ev), "türlere_göre": counts,
            "örnekler": [{"olay": e["ad"], "tür": e["tür_tr"], "tarih": e["son"][2]} for e in ev[:12]], "kaynak": "NASA EONET"}


def firms(days=1, area="world"):
    key = env("FIRMS_MAP_KEY")
    if not key:
        raise RuntimeError("NASA FIRMS yangın noktaları için ücretsiz anahtar gerekli: firms.modaps.eosdis.nasa.gov/api/map_key → .env FIRMS_MAP_KEY")

    def load():
        csv = _http_get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{area}/{int(days)}", timeout=60)
        lines = csv.strip().splitlines()
        hdr = lines[0].split(",")
        ia, io, ifrp = hdr.index("latitude"), hdr.index("longitude"), hdr.index("frp") if "frp" in hdr else None
        pts = []
        for ln in lines[1:]:
            f = ln.split(",")
            try:
                pts.append([round(float(f[ia]), 3), round(float(f[io]), 3), float(f[ifrp]) if ifrp is not None else 1])
            except Exception:
                pass
        return pts[:30000]
    return _cached(f"firms{days}{area}", 3600, load)


def fires_tool(days=1):
    p = firms(days)
    return {"ui": "globe_layer", "layer": "fires", "on": True, "nokta": len(p), "kaynak": "NASA FIRMS VIIRS"}


def gibs_image(date=""):
    """NASA GIBS: belirtilen günün (varsayılan dün) tüm Dünya gerçek renkli uydu mozaiği (2048×1024, eşdikdörtgen)."""
    import datetime as dt
    d = date or (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    f = DATA / "gibs" / f"{d}.jpg"
    if f.exists():
        return f.read_bytes(), d
    f.parent.mkdir(exist_ok=True)
    q = {"SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": "VIIRS_SNPP_CorrectedReflectance_TrueColor", "CRS": "EPSG:4326",
         "BBOX": "-90,-180,90,180", "WIDTH": 2048, "HEIGHT": 1024, "FORMAT": "image/jpeg", "TIME": d}
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?" + urllib.parse.urlencode(q),
                                                       headers={"User-Agent": "JARVIS"}), timeout=90) as r:
        data = r.read()
    if data[:2] != b"\xff\xd8":
        raise RuntimeError("GIBS görüntü vermedi: " + data[:200].decode("utf-8", "ignore"))
    f.write_bytes(data)
    return data, d


def satellite_today(date=""):
    return {"ui": "globe_layer", "layer": "gibs", "on": True, "date": date, "kaynak": "NASA GIBS (VIIRS gerçek renk)",
            "not": "Dünün tüm Dünya uydu mozaiği kürenin üzerine giydirilir; bulutlar gerçektir."}


def radar_info():
    d = _cached("rv", 300, lambda: json.loads(_http_get("https://api.rainviewer.com/public/weather-maps.json", timeout=20)))
    frames = d.get("radar", {}).get("past", []) + d.get("radar", {}).get("nowcast", [])
    return {"host": d.get("host"), "frames": [{"time": f["time"], "path": f["path"]} for f in frames]}


def weather_radar(place="Istanbul"):
    from .geo import geocode
    g = geocode(place)
    return {"ui": "map", **g, "uydu": False, "radar": True, "kaynak": "RainViewer"}


# ---------- haber haritası ----------
EDITIONS = [("TR", "tr", "Türkiye"), ("US", "en", "ABD"), ("GB", "en", "Birleşik Krallık"), ("DE", "de", "Almanya"), ("FR", "fr", "Fransa"),
            ("RU", "ru", "Rusya"), ("UA", "uk", "Ukrayna"), ("IL", "he", "İsrail"), ("EG", "ar", "Mısır"), ("IN", "en", "Hindistan"),
            ("JP", "ja", "Japonya"), ("KR", "ko", "Güney Kore"), ("AU", "en", "Avustralya"), ("BR", "pt-BR", "Brezilya"), ("MX", "es-419", "Meksika"),
            ("ZA", "en", "Güney Afrika"), ("NG", "en", "Nijerya"), ("SA", "ar", "Suudi Arabistan"), ("IT", "it", "İtalya"), ("ES", "es", "İspanya"),
            ("CN", "zh-Hans", "Çin"), ("CA", "en", "Kanada"), ("ID", "id", "Endonezya"), ("AR", "es-419", "Arjantin")]


def news_map(topic="", per_country=3):
    import re
    from concurrent.futures import ThreadPoolExecutor
    from .geo import find_country, _capital

    def one(ed):
        gl, hl, name = ed
        base = "https://news.google.com/rss"
        url = (f"{base}/search?" + urllib.parse.urlencode({"q": topic, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"})) if topic else f"{base}?hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
        try:
            xml = _http_get(url, timeout=15)
        except Exception:
            return None
        import html as H
        items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>", xml, re.S)[: int(per_country)]
        c = find_country(name)
        cap = _capital(c) if c else None
        lat, lon = (cap["lat"], cap["lon"]) if cap else ((c["ly"], c["lx"]) if c else (0, 0))
        return {"ülke": name, "lat": lat, "lon": lon, "haberler": [{"başlık": H.unescape(t), "link": l, "tarih": d[5:22]} for t, l, d in items]}
    with ThreadPoolExecutor(8) as ex:
        res = [r for r in ex.map(one, EDITIONS) if r and r["haberler"]]
    return res


def news_map_tool(topic=""):
    res = _cached(f"news{topic}", 900, lambda: news_map(topic))
    return {"ui": "globe_layer", "layer": "news", "on": True, "topic": topic, "ülke_sayısı": len(res),
            "özet": [{"ülke": r["ülke"], "manşet": r["haberler"][0]["başlık"]} for r in res[:12]]}


# ---------- AIS canlı gemi trafiği (aisstream.io, ücretsiz anahtar) ----------
class _WS:
    """Standart kütüphaneyle minimal güvenli websocket istemcisi (RFC 6455)."""

    def __init__(self, host, path, port=443, tls=True, timeout=15):
        raw = socket.create_connection((host, port), timeout=timeout)
        self.s = ssl.create_default_context().wrap_socket(raw, server_hostname=host) if tls else raw
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.s.recv(1024)
            if not chunk:
                raise ConnectionError("websocket el sıkışması başarısız")
            resp += chunk
        if b" 101 " not in resp.split(b"\r\n")[0]:
            raise ConnectionError(resp.split(b"\r\n")[0].decode())
        self.buf = resp.split(b"\r\n\r\n", 1)[1]

    def send(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("bağlantı kapandı")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if b2 & 0x80:
                self._read(4)
            data = self._read(n)
            if op == 0x8:
                raise ConnectionError("sunucu kapattı")
            if op == 0x9:
                continue
            msg += data
            if b1 & 0x80:
                return msg.decode("utf-8", "ignore")

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def ships_live(lat1=30, lon1=-10, lat2=47, lon2=42, seconds=20, limit=1500):
    key = env("AISSTREAM_KEY")
    if not key:
        raise RuntimeError("Canlı gemi trafiği için ücretsiz anahtar gerekli: aisstream.io → .env AISSTREAM_KEY")

    def load():
        ws = _WS("stream.aisstream.io", "/v0/stream")
        ws.send(json.dumps({"APIKey": key, "BoundingBoxes": [[[float(lat1), float(lon1)], [float(lat2), float(lon2)]]], "FilterMessageTypes": ["PositionReport"]}))
        ships, t0 = {}, time.time()
        ws.s.settimeout(5)
        try:
            while time.time() - t0 < float(seconds) and len(ships) < int(limit):
                try:
                    m = json.loads(ws.recv())
                except socket.timeout:
                    continue
                if "error" in m:
                    raise RuntimeError(m["error"])
                md, pr = m.get("MetaData", {}), m.get("Message", {}).get("PositionReport", {})
                if md.get("Latitude") is None:
                    continue
                ships[md.get("MMSI")] = {"ad": (md.get("ShipName") or "").strip(), "mmsi": md.get("MMSI"), "lat": md["Latitude"], "lon": md["Longitude"],
                                         "hız_knot": pr.get("Sog"), "rota": pr.get("Cog")}
        finally:
            ws.close()
        return list(ships.values())
    return _cached(f"ais{lat1}{lon1}{lat2}{lon2}", 120, load)


def ships_tool(region="akdeniz"):
    boxes = {"akdeniz": (30, -6, 46, 37), "türkiye": (35, 25, 43, 42), "karadeniz": (40.5, 27, 47, 42), "boğaz": (40.8, 28.8, 41.4, 29.3),
             "kuzey avrupa": (48, -5, 60, 15), "basra": (22, 47, 31, 57), "süveyş": (27, 31.5, 32, 34), "singapur": (0, 100, 5, 106)}
    b = boxes.get(region.lower(), boxes["akdeniz"])
    s = ships_live(*b)
    return {"ui": "globe_layer", "layer": "ships_live", "on": True, "bölge": region, "box": b, "gemi": len(s), "kaynak": "aisstream.io (AIS)"}


TOOLS = {
    "world_events": (world_events, _schema("Dünyadaki güncel doğal olaylar (NASA EONET): orman yangınları, fırtına/kasırgalar (rotasıyla), seller, volkanlar, toz fırtınaları; kürede gösterir.",
                                           {"category": S("tür: yangın, fırtına, sel, volkan, toz... (boş: hepsi)"), "days": N("son kaç gün")}), False),
    "fires_map": (fires_tool, _schema("Uydudan tespit edilen aktif yangın noktaları (NASA FIRMS, son 1-7 gün).", {"days": N("gün")}), False),
    "satellite_today": (satellite_today, _schema("Dünyanın dünkü gerçek uydu görüntüsünü (NASA GIBS) kürenin üzerine giydirir.", {"date": S("YYYY-AA-GG (boş: dün)")}), False),
    "weather_radar": (weather_radar, _schema("Bir bölgenin canlı yağış radarını haritada açar (RainViewer).", {"place": S("yer")}), False),
    "news_map": (news_map_tool, _schema("Dünyanın her yerinden haberleri ülkelerine göre kürede gösterir (bir konu verilirse o konu).", {"topic": S("konu (boş: manşetler)")}), False),
    "ships_live": (ships_tool, _schema("Canlı gemi trafiği (AIS): akdeniz, türkiye, karadeniz, boğaz, süveyş, basra, kuzey avrupa, singapur.", {"region": S("bölge")}), False),
}
