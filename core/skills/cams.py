"""JARVIS'in gözleri: eski bir telefonu kamera yap (Ayarlar > PLATFORMLAR > 'Bu cihazı kamera yap' ya da adres sonuna ?rol=kamera).
Telefon saniyede ~1 kare gönderir; bilgisayarda/tablette canlı izlenir. "mutfakta ne var?" deyince JARVIS son kareye bakıp yorumlar.
Güvenlik modu: hareket algılanınca bildirim + Telegram'a fotoğraf.
GİZLİLİK: kareler diske/loga yazılmaz; yalnızca SON kare bellekte tutulur, kamera kapanınca silinir.
Hareket algılama telefonda yapılır (küçük gri karelerin farkı); modele kare yalnızca sen sorduğunda gider."""
import re
import threading
import time

from .. import llm, memory
from ..config import load_settings, save_settings
from ..tools import S, _schema

CAMS = {}          # id -> {name, loc, frame, ts, w, h, motion_ts, want_hd_until, viewers}
_lock = threading.Lock()
OFFLINE = 12       # sn: bu süre kare gelmezse çevrimdışı
_last_alert = {}


def _norm(s):
    s = (s or "").lower().strip()
    for a, b in (("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c"), ("â", "a")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", s)


def put_frame(cid, data, name="", loc="", motion=False, w=0, h=0):
    now = time.time()
    with _lock:
        c = CAMS.setdefault(cid, {"name": name or cid, "loc": loc or "", "frame": b"", "ts": 0, "motion_ts": 0, "want_hd_until": 0, "viewers": {}})
        c.update({"frame": data, "ts": now, "w": w, "h": h})
        if name:
            c["name"] = name
        if loc:
            c["loc"] = loc
        if motion:
            c["motion_ts"] = now
        viewers = sum(1 for t in c["viewers"].values() if now - t < 6)
        hd = now < c["want_hd_until"]
    if motion:
        _on_motion(cid)
    return {"hd": hd, "viewers": viewers, "security": bool(load_settings().get("cam_security"))}


def _gc():
    now = time.time()
    with _lock:
        for cid in [k for k, c in CAMS.items() if now - c["ts"] > 120]:
            CAMS.pop(cid, None)  # uzun süre kapalı kameranın son karesini de sil


def list_cams():
    _gc()
    now = time.time()
    with _lock:
        return [{"id": k, "name": c["name"], "loc": c["loc"], "online": now - c["ts"] < OFFLINE, "age": round(now - c["ts"], 1),
                 "motion": now - c["motion_ts"] < 5, "w": c.get("w"), "h": c.get("h")} for k, c in CAMS.items()]


def frame(cid, viewer=""):
    with _lock:
        c = CAMS.get(cid)
        if not c:
            return None
        if viewer:
            c["viewers"][viewer] = time.time()
        return c["frame"]


def _find(location=""):
    cams = [c for c in list_cams() if c["online"]]
    if not cams:
        return None, "Bağlı kamera yok. Telefonu kamera yapmak için: Ayarlar > PLATFORMLAR > 'Bu cihazı kamera yap'."
    if not location:
        return cams[0], ""
    q = _norm(location)
    for c in cams:
        if q and (q in _norm(c["loc"]) or q in _norm(c["name"]) or _norm(c["loc"]) in q):
            return c, ""
    offline = [c for c in CAMS.values() if q and (q in _norm(c["loc"]) or q in _norm(c["name"]))]
    if offline:
        return None, f"{offline[0]['name']} çevrimdışı."
    return None, f"'{location}' adında bir kamera yok. Bağlı kameralar: " + ", ".join(f"{c['name']} ({c['loc'] or 'konumsuz'})" for c in cams)


def room_camera_look(question="Ne görüyorsun?", location=""):
    """Telefon kamerasından anlık kareye bakıp soruyu cevaplar."""
    c, err = _find(location)
    if not c:
        if not location and not CAMS:  # telefon kamerası yok: bilgisayarın kamerasına bak
            try:
                from .computer import camera_look
                return camera_look(question)
            except Exception:
                pass
        return err
    with _lock:
        CAMS[c["id"]]["want_hd_until"] = time.time() + 8  # bir sonraki kare yüksek çözünürlük gelsin
        start = CAMS[c["id"]]["ts"]
    for _ in range(25):  # taze (yüksek çözünürlüklü) kareyi en fazla 5 sn bekle
        time.sleep(0.2)
        if CAMS.get(c["id"], {}).get("ts", 0) > start:
            break
    img = frame(c["id"])
    if not img or time.time() - CAMS.get(c["id"], {}).get("ts", 0) > OFFLINE:
        return f"{c['name']} yanıt vermedi."
    prompt = (f"Bu kare evdeki '{c['loc'] or c['name']}' kamerasından. Soru: {question}\n"
              "Yalnızca karede gerçekten görüneni söyle; emin değilsen 'net göremiyorum' de. Kişileri adıyla tanımlamaya çalışma. "
              "Kısa, sesli okunacak Türkçe cevap ver.")
    try:
        return f"[{c['name']} · {c['loc']}] " + llm.vision(prompt, img, "image/jpeg")
    except Exception as e:
        return f"Kare analiz edilemedi: {e}"


def room_camera_list():
    cams = list_cams()
    if not cams:
        return "Bağlı kamera yok."
    return [{"ad": c["name"], "konum": c["loc"], "durum": "çevrimiçi" if c["online"] else "çevrimdışı", "hareket": c["motion"]} for c in cams]


def security_mode(on=True):
    """Güvenlik modu: kameralarda hareket olunca bildirim + Telegram'a fotoğraf."""
    on = on if isinstance(on, bool) else str(on).lower() not in ("false", "0", "kapat", "hayır")
    save_settings({"cam_security": on})
    return "Güvenlik modu " + ("AÇIK: kameralarda hareket olursa haber vereceğim ve Telegram'a fotoğraf göndereceğim." if on else "kapalı.")


def _on_motion(cid):
    if not load_settings().get("cam_security"):
        return
    now = time.time()
    if now - _last_alert.get(cid, 0) < 60:  # dakikada en fazla bir uyarı
        return
    _last_alert[cid] = now
    c = CAMS.get(cid) or {}
    text = f"🚨 Hareket algılandı: {c.get('name', cid)} · {c.get('loc', '')} ({time.strftime('%H:%M:%S')})"
    memory.notify(text, "security")

    def send():
        try:
            from .. import telegram_bot
            from ..config import env
            if not env("TELEGRAM_BOT_TOKEN"):
                return
            for chat in telegram_bot._allowed():
                telegram_bot._send_file("sendPhoto", "photo", chat, c.get("frame", b""), "hareket.jpg", "image/jpeg", text)
        except Exception as e:
            print("[kamera güvenlik]", e)
    threading.Thread(target=send, daemon=True).start()


GROUP = "cams"
TOOLS = {
    "room_camera_look": (room_camera_look, _schema("Evdeki telefon kamerasından (JARVIS'in gözü) anlık kareye bakıp soruyu cevaplar: 'mutfakta ne var', 'kapıya bak', 'fincan var mı'.",
                                         {"question": S("soru"), "location": S("kamera konumu/adı (mutfak, salon, kapı…) — boşsa ilk kamera")}, ["question"]), False),
    "room_camera_list": (room_camera_list, _schema("Bağlı kameraları ve durumlarını listeler."), False),
    "security_mode": (security_mode, _schema("Güvenlik modu: kameralarda hareket olunca bildirim + Telegram fotoğrafı.", {"on": {"type": "boolean"}}), False),
}
