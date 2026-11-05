"""TELEFON EKRANLARI + ARAMA + SİSTEM KİLİDİ
• Eski telefonlar "ekran" olur: telefonda JARVIS adresini ?rol=ekran ile aç (Ayarlar > PLATFORMLAR'daki adres + anahtar).
  JARVIS onlara komut yollar: YouTube videosu oynat (hepsinde aynı ya da her birinde farklı), yazı göster, sesli konuş,
  animasyon oynat, telefonu çaldır (JARVIS seni arar), durdur.
• JARVIS'i ara: arama ekranı açılır, kesintisiz sesli konuşma (dinle → düşün → konuş → dinle). Telefondan ya da bilgisayardan.
• Sistem kilidi: "SİSTEM KİLİTLİ" ekranı; iki elle çimdikleyip açarak (kamera), PIN ya da tıklayarak açılır.
Kayıtlar bellekte tutulur; telefon sayfası kapanınca 30 sn sonra listeden düşer."""
import threading
import time
import uuid

from ..tools import S, _schema

_LOCK = threading.Lock()
SCREENS = {}          # id → {"name", "seen", "queue": [cmd], "state"}
ONLINE_S = 30


def register(sid, name="", state=""):
    """Telefon sayfası her yoklamada çağırır; bekleyen komutları teslim eder."""
    sid = (sid or "")[:40]
    if not sid:
        return []
    with _LOCK:
        s = SCREENS.setdefault(sid, {"name": name or sid, "seen": 0, "queue": [], "state": ""})
        if name:
            s["name"] = name[:40]
        if state:
            s["state"] = state[:80]
        s["seen"] = time.time()
        out, s["queue"] = s["queue"], []
    return out


def online():
    now = time.time()
    with _LOCK:
        return {k: v for k, v in SCREENS.items() if now - v["seen"] < ONLINE_S}


def _targets(target):
    on = online()
    t = (target or "").strip().lower()
    if not t or t in ("hepsi", "tümü", "tumu", "all", "hepsinde", "tüm telefonlar"):
        return list(on)
    hit = [k for k, v in on.items() if t == k.lower() or t in v["name"].lower()]
    if hit:
        return hit
    if t.isdigit() and 0 < int(t) <= len(on):  # "2. telefon"
        return [sorted(on, key=lambda k: on[k]["name"])[int(t) - 1]]
    return []


def push(target, cmd):
    ids = _targets(target)
    cmd = dict(cmd, cid=uuid.uuid4().hex[:8], t=time.time())
    with _LOCK:
        for i in ids:
            SCREENS[i]["queue"].append(cmd)
    return ids


def _names(ids):
    on = online()
    return [on[i]["name"] for i in ids if i in on]


NO_PHONE = ("Bağlı telefon ekranı yok. Telefonda JARVIS adresini sonuna ?rol=ekran ekleyerek aç "
            "(bilgisayarda JARVIS --lan ile çalışmalı; adres ve anahtar Ayarlar > PLATFORMLAR'da).")


def phone_screens():
    """Bağlı telefon ekranlarını listeler."""
    on = online()
    if not on:
        return {"telefonlar": [], "not": NO_PHONE}
    return {"telefonlar": [{"ad": v["name"], "durum": v["state"] or "hazır", "son": f"{int(time.time() - v['seen'])} sn önce"} for v in on.values()]}


def phone_video(query, target="hepsi"):
    """Telefon(lar)da YouTube videosu oynatır. 'a | b | c' yazılırsa her telefona sırayla farklı video gider."""
    ids = _targets(target)
    if not ids:
        return {"error": NO_PHONE if not online() else f"'{target}' adlı telefon bulunamadı. Bağlı: {', '.join(_names(list(online())))}"}
    from .media import youtube_search
    queries = [q.strip() for q in str(query).split("|") if q.strip()] or [str(query)]
    sent = []
    cache = {}
    for n, sid in enumerate(sorted(ids, key=lambda k: SCREENS[k]["name"])):
        q = queries[n % len(queries)]
        if q not in cache:
            try:
                cache[q] = youtube_search(q, n=1)
            except Exception as e:
                cache[q] = []
                err = str(e)
        if not cache[q]:
            continue
        v = cache[q][0]
        push(sid, {"type": "video", "id": v["id"], "title": v["title"], "channel": v["channel"]})
        sent.append({"telefon": SCREENS[sid]["name"], "video": v["title"], "kanal": v["channel"]})
    if not sent:
        return {"error": "Video bulunamadı."}
    return {"ok": True, "oynatılıyor": sent}


def phone_say(text, target="hepsi"):
    ids = push(target, {"type": "say", "text": str(text)[:600]})
    return {"ok": True, "telefonlar": _names(ids)} if ids else {"error": NO_PHONE}


def phone_show(text, target="hepsi"):
    ids = push(target, {"type": "show", "text": str(text)[:400]})
    return {"ok": True, "telefonlar": _names(ids)} if ids else {"error": NO_PHONE}


def phone_anim(preset="galaxy", target="hepsi"):
    from .stage import _guess, PRESETS
    p = (preset or "").lower()
    p = p if p in PRESETS else (_guess(p) or "galaxy")
    ids = push(target, {"type": "anim", "preset": p})
    return {"ok": True, "animasyon": p, "telefonlar": _names(ids)} if ids else {"error": NO_PHONE}


def phone_stop(target="hepsi"):
    ids = push(target, {"type": "stop"})
    return {"ok": True, "telefonlar": _names(ids)} if ids else {"error": NO_PHONE}


def call_me(message="", target=""):
    """JARVIS seni arar: telefonda (ekran rolündeki) ya da bilgisayarda gelen arama ekranı çalar; açınca sesli görüşme başlar."""
    msg = str(message or "")[:400]
    if target or online():
        ids = push(target or "hepsi", {"type": "ring", "text": msg})
        if ids:
            return {"ok": True, "çalan": _names(ids), "not": "Telefon çalıyor; açınca mesajı sesli söyleyip dinlemeye geçer."}
    return {"ui": "call", "incoming": True, "message": msg, "not": "Bilgisayarda gelen arama ekranı açıldı."}


def voice_call():
    """Sesli arama modunu açar (kesintisiz konuşma)."""
    return {"ui": "call", "incoming": False}


def system_lock(on=True):
    """'SİSTEM KİLİTLİ' ekranı. Açmak: iki elle çimdikle-aç (kamera), PIN ya da tıkla."""
    if isinstance(on, str):
        on = on.lower() not in ("false", "0", "hayır", "kapat", "aç", "ac", "off")
    return {"ui": "lock", "on": bool(on)}


GROUP = "screens"
TOOLS = {
    "phone_screens": (phone_screens, _schema("Bağlı telefon ekranlarını (?rol=ekran) listeler."), False),
    "phone_video": (phone_video, _schema("Telefon ekran(lar)ında YouTube videosu oynatır. Her telefona farklı video için sorguları '|' ile ayır.",
                                         {"query": S("ne aransın (ör. 'never gonna give you up' ya da 'a | b | c')"), "target": S("telefon adı ya da 'hepsi'")}, ["query"]), False),
    "phone_say": (phone_say, _schema("Telefon(lar)da sesli konuşur.", {"text": S("söylenecek"), "target": S("telefon adı ya da 'hepsi'")}, ["text"]), False),
    "phone_show": (phone_show, _schema("Telefon ekran(lar)ında büyük yazı/bildirim gösterir.", {"text": S("yazı"), "target": S("telefon adı ya da 'hepsi'")}, ["text"]), False),
    "phone_anim": (phone_anim, _schema("Telefon ekran(lar)ında animasyon oynatır (solar, atom, dna, heart, galaxy, fireworks, matrix, waves, clock).",
                                       {"preset": S("animasyon"), "target": S("telefon adı ya da 'hepsi'")}), False),
    "phone_stop": (phone_stop, _schema("Telefon ekranlarındaki videoyu/animasyonu durdurup bekleme ekranına döner.", {"target": S("telefon adı ya da 'hepsi'")}), False),
    "call_me": (call_me, _schema("JARVIS kullanıcıyı ARAR: telefonda/bilgisayarda gelen arama ekranı çalar, açınca mesajı söyler ve sesli görüşme başlar.",
                                 {"message": S("açınca söylenecek ilk cümle"), "target": S("telefon adı (boş: bağlı telefon varsa onlar, yoksa bilgisayar)")}), False),
    "voice_call": (voice_call, _schema("Sesli arama/görüşme modunu açar (eller serbest, kesintisiz konuşma)."), False),
    "system_lock": (system_lock, _schema("'SİSTEM KİLİTLİ' ekranını açar/kapatır (iki elle çimdikle-aç hareketiyle, PIN'le ya da tıklayarak açılır).",
                                         {"on": {"type": "boolean"}}), False),
}
