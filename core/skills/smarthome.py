"""Akıllı ev ve fiziksel cihazlar.

- Home Assistant: hemen her marka (Philips Hue, Xiaomi, Tuya/Smart Life, Sonoff, TP-Link, Samsung TV,
  LG, klima, termostat, kamera, kapı sensörü...) tek yerden. .env: HA_URL, HA_TOKEN
- Arduino / Raspberry Pi / robot: seri port (pyserial) veya ağdaki cihaza HTTP komutu.
- 3D yazıcı: OctoPrint. .env: OCTOPRINT_URL, OCTOPRINT_KEY
"""
import json
import urllib.error
import urllib.request

from ..config import env
from ..tools import N, S, _schema


def _req(url, method="GET", body=None, headers=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return json.loads(raw) if raw else {}
            except Exception:
                return raw.decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")


# ===================== Home Assistant =====================
def _ha(path, method="GET", body=None):
    url, tok = env("HA_URL").rstrip("/"), env("HA_TOKEN")
    if not url or not tok:
        raise RuntimeError("Home Assistant bağlı değil. .env'ye HA_URL (örn http://homeassistant.local:8123) ve HA_TOKEN (Profil > Uzun ömürlü erişim jetonu) ekle.")
    return _req(url + "/api/" + path, method, body, {"Authorization": f"Bearer {tok}"})


DOMAINS = {"ışık": "light", "lamba": "light", "priz": "switch", "anahtar": "switch", "klima": "climate",
           "termostat": "climate", "tv": "media_player", "televizyon": "media_player", "hoparlör": "media_player",
           "sensör": "sensor", "kapı": "binary_sensor", "kamera": "camera", "perde": "cover", "fan": "fan",
           "kilit": "lock", "süpürge": "vacuum", "senaryo": "scene", "otomasyon": "automation"}


def home_devices(kind="", query=""):
    states = _ha("states")
    dom = DOMAINS.get(kind.lower(), kind.lower())
    out = []
    for s in states:
        eid = s["entity_id"]
        name = s.get("attributes", {}).get("friendly_name", eid)
        if dom and not eid.startswith(dom + "."):
            continue
        if query and query.lower() not in (eid + " " + name).lower():
            continue
        a = s.get("attributes", {})
        extra = {k: a[k] for k in ("brightness", "temperature", "current_temperature", "unit_of_measurement", "hvac_mode") if k in a}
        out.append({"id": eid, "ad": name, "durum": s["state"], **extra})
    return out[:80] or "Cihaz bulunamadı."


def _find_entity(name):
    if "." in name and " " not in name:
        return name
    for s in _ha("states"):
        fn = s.get("attributes", {}).get("friendly_name", "")
        if name.lower() in fn.lower() or name.lower() in s["entity_id"].lower():
            return s["entity_id"]
    raise RuntimeError(f"'{name}' adlı cihaz bulunamadı.")


def home_control(device, action="toggle", value=""):
    """action: on | off | toggle | brightness (0-100) | temperature | color | volume | open | close | lock | unlock | activate"""
    eid = _find_entity(device)
    dom = eid.split(".")[0]
    data = {"entity_id": eid}
    svc = {"on": "turn_on", "off": "turn_off", "toggle": "toggle", "open": "open_cover", "close": "close_cover",
           "lock": "lock", "unlock": "unlock", "activate": "turn_on"}.get(action)
    if action == "brightness":
        svc, data["brightness_pct"] = "turn_on", int(float(value))
    elif action == "temperature":
        svc, data["temperature"] = "set_temperature", float(value)
    elif action == "color":
        svc, data["color_name"] = "turn_on", str(value)
    elif action == "volume":
        svc, data["volume_level"] = "volume_set", float(value) / 100
    if not svc:
        return "Geçersiz eylem."
    if dom in ("scene", "script") and svc == "turn_on":
        pass
    _ha(f"services/{dom}/{svc}", "POST", data)
    return f"{device}: {action}{' ' + str(value) if value != '' else ''} yapıldı."


def home_scenario(name):
    """Home Assistant'taki bir senaryo/otomasyon/script'i çalıştırır (örn 'film modu', 'iyi geceler')."""
    eid = _find_entity(name)
    dom = eid.split(".")[0]
    svc = {"scene": "turn_on", "script": "turn_on", "automation": "trigger"}.get(dom, "turn_on")
    _ha(f"services/{dom}/{svc}", "POST", {"entity_id": eid})
    return f"Senaryo çalıştı: {name}"


# ===================== Arduino / Raspberry Pi / robot =====================
def serial_ports():
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError:
        return "pyserial gerekli (requirements-extra.txt)."
    return [{"port": p.device, "açıklama": p.description} for p in list_ports.comports()] or "Seri cihaz yok."


def serial_send(port, command, baud=9600, read_reply=True):
    try:
        import serial  # type: ignore
    except ImportError:
        return "pyserial gerekli."
    import time
    with serial.Serial(port, int(baud), timeout=2) as s:
        time.sleep(1.8)  # Arduino reset bekleme
        s.write((command.strip() + "\n").encode())
        if read_reply:
            time.sleep(0.4)
            return f"Gönderildi. Cevap: {s.read_all().decode('utf-8', 'ignore').strip() or '(yok)'}"
    return "Gönderildi."


def device_http(url, method="GET", body=""):
    """Ağdaki bir cihaza (ESP32, Raspberry Pi, robot) HTTP komutu gönderir."""
    b = None
    if body:
        try:
            b = json.loads(body)
        except Exception:
            b = {"komut": body}
    return _req(url, method.upper(), b)


# ===================== 3D yazıcı =====================
def printer3d(action="status"):
    url, key = env("OCTOPRINT_URL").rstrip("/"), env("OCTOPRINT_KEY")
    if not url:
        return "OctoPrint bağlı değil (.env: OCTOPRINT_URL, OCTOPRINT_KEY)."
    h = {"X-Api-Key": key}
    if action == "status":
        j = _req(url + "/api/job", headers=h)
        p = _req(url + "/api/printer", headers=h)
        return {"dosya": j.get("job", {}).get("file", {}).get("name"), "ilerleme_%": round(j.get("progress", {}).get("completion") or 0, 1),
                "kalan_dk": round((j.get("progress", {}).get("printTimeLeft") or 0) / 60), "durum": j.get("state"),
                "sıcaklık": p.get("temperature", {})}
    cmd = {"pause": {"command": "pause", "action": "pause"}, "resume": {"command": "pause", "action": "resume"},
           "cancel": {"command": "cancel"}}.get(action)
    if not cmd:
        return "Geçersiz eylem."
    _req(url + "/api/job", "POST", cmd, h)
    return f"3D yazıcı: {action}"


TOOLS = {
    "home_devices": (home_devices, _schema("Akıllı ev cihazlarını ve durumlarını listeler (ışık, priz, klima, TV, sensör, kapı, kamera...).",
                                           {"kind": S("ışık, priz, klima, tv, sensör, kapı... (boş=hepsi)"), "query": S("isim arama")}), False),
    "home_control": (home_control, _schema("Akıllı ev cihazını kontrol eder.",
                                           {"device": S("cihaz adı (örn 'salon lambası')"),
                                            "action": {"type": "string", "enum": ["on", "off", "toggle", "brightness", "temperature", "color", "volume", "open", "close", "lock", "unlock"]},
                                            "value": S("parlaklık %, sıcaklık, renk adı, ses %")}, ["device", "action"]),
                     lambda a: a.get("action") in ("unlock", "open")),
    "home_scenario": (home_scenario, _schema("Ev senaryosu çalıştırır (film modu, iyi geceler, evden çıkış...).", {"name": S("senaryo adı")}, ["name"]), False),
    "serial_ports": (serial_ports, _schema("Bağlı Arduino/seri cihazları listeler."), False),
    "serial_send": (serial_send, _schema("Arduino/robot/seri cihaza komut gönderir.",
                                         {"port": S("COM3 gibi"), "command": S("komut"), "baud": N("hız")}, ["port", "command"]), True),
    "device_http": (device_http, _schema("Ağdaki bir cihaza (ESP32, Raspberry Pi, robot) HTTP komutu gönderir.",
                                         {"url": S("adres"), "method": S("GET/POST"), "body": S("JSON")}, ["url"]), True),
    "printer3d": (printer3d, _schema("3D yazıcı (OctoPrint) durumu / duraklat / devam / iptal.",
                                     {"action": {"type": "string", "enum": ["status", "pause", "resume", "cancel"]}}),
                  lambda a: a.get("action") == "cancel"),
}
