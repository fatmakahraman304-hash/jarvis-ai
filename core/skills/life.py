"""YAŞAM: toplantı asistanı, odak modu (pomodoro), günlük, bitki doktoru + sulama hatırlatıcısı, nesnelere yapışkan not,
"aydınlat beni" sahneli haber brifingi, AR oyunları (taş-kağıt-makas, balon patlatma) skorları."""
import json
import re
import threading
import time

from .. import llm
from ..config import DATA
from ..tools import N, S, _schema

FILE = DATA / "yasam.json"
_lock = threading.Lock()


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"journal": [], "focus": [], "plants": [], "games": {}, "meetings": []}


def _save(d):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _obj(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def _ask(prompt, light=True):
    from .. import brain
    return brain.ask(prompt, light=light)


# ================= TOPLANTI ASİSTANI =================
def meeting_chunk(wav):
    """Toplantı kaydının bir parçası (≈15 sn) → yazı."""
    from .media import transcribe_bytes
    return transcribe_bytes(wav, "parca.wav", "audio/wav", "tr")


def meeting_finish(transcript, title="", add_todos=True):
    """Döküm → özet, kararlar, yapılacaklar; Belgeler/JARVIS toplantıları'na .md olarak kaydedilir; yapılacaklar listeye eklenir."""
    transcript = (transcript or "").strip()
    if len(transcript) < 20:
        return {"error": "Döküm çok kısa."}
    prompt = ("Aşağıda bir toplantının otomatik dökümü var (konuşmacılar ayrılmamış, yazım hataları olabilir). Türkçe JSON ver: "
              '{"başlık": "kısa", "özet": "4-6 cümle", "konular": ["..."], "kararlar": ["..."], '
              '"yapılacaklar": [{"iş": "...", "kim": "dökümde geçiyorsa", "tarih": "dökümde geçiyorsa"}], "açık_sorular": ["..."]}. '
              "Dökümde olmayan hiçbir şeyi ekleme. Yalnızca JSON.\n\nDÖKÜM:\n" + transcript[:60000])
    d = _obj(_ask(prompt, light=False)) or {"özet": "Özet çıkarılamadı."}
    title = title or d.get("başlık") or time.strftime("Toplantı %d.%m.%Y %H:%M")
    md = [f"# {title}", f"*{time.strftime('%d.%m.%Y %H:%M')} · JARVIS toplantı asistanı*", "", "## Özet", d.get("özet", "")]
    for k, h in (("konular", "Konular"), ("kararlar", "Kararlar"), ("açık_sorular", "Açık sorular")):
        if d.get(k):
            md += ["", f"## {h}"] + [f"- {x}" for x in d[k]]
    todos = [t for t in d.get("yapılacaklar") or [] if isinstance(t, dict) and t.get("iş")]
    if todos:
        md += ["", "## Yapılacaklar"] + [f"- [ ] {t['iş']}" + (f" — {t['kim']}" if t.get("kim") else "") + (f" ({t['tarih']})" if t.get("tarih") else "") for t in todos]
    md += ["", "## Döküm", transcript]
    from ..tools import _path
    folder = _path("belgeler") / "JARVIS toplantıları"
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / (re.sub(r"[^\w\- ]+", "", title).strip()[:60] + time.strftime(" %Y%m%d_%H%M") + ".md")
    f.write_text("\n".join(md), encoding="utf-8")
    added = 0
    if add_todos and todos:
        from .automation import todo_add
        for t in todos[:15]:
            todo_add(t["iş"] + (f" ({t['kim']})" if t.get("kim") else ""))
            added += 1
    with _lock:
        s = _load(); s.setdefault("meetings", []).append({"title": title, "file": str(f), "ts": time.time()}); _save(s)
    return {**d, "başlık": title, "dosya": str(f), "eklenen_iş": added}


def meeting_mode(action="start", title=""):
    return {"ui": "meeting", "action": "stop" if (action or "").lower() in ("stop", "bitir", "durdur", "kapat") else "start", "title": title,
            "not": "Toplantı asistanı: canlı altyazı açıldı; bitince özet, kararlar ve yapılacaklar çıkarılıp kaydedilecek."}


# ================= ODAK MODU =================
def focus_mode(minutes=25, task="", breaks=5):
    return {"ui": "focus", "minutes": max(1, min(180, int(minutes or 25))), "task": task, "break": int(breaks or 5),
            "not": f"Odak modu: {int(minutes or 25)} dk. Bildirimler susturuldu; bitince mola hatırlatılacak."}


def focus_log(minutes, task="", done=True):
    with _lock:
        s = _load(); s.setdefault("focus", []).append({"m": float(minutes), "task": task, "done": bool(done), "ts": time.time()}); _save(s)
    return focus_stats()


def focus_stats():
    s = _load(); now = time.time()
    day = [f for f in s.get("focus", []) if now - f["ts"] < 86400 and time.strftime("%Y%m%d", time.localtime(f["ts"])) == time.strftime("%Y%m%d")]
    week = [f for f in s.get("focus", []) if now - f["ts"] < 7 * 86400]
    return {"bugün_dk": round(sum(f["m"] for f in day)), "bugün_oturum": sum(1 for f in day if f["done"]),
            "hafta_dk": round(sum(f["m"] for f in week)), "hafta_oturum": sum(1 for f in week if f["done"])}


# ================= GÜNLÜK =================
def journal_add(text, mood=""):
    """Günlüğe yazar (yalnızca bu bilgisayarda saklanır)."""
    with _lock:
        s = _load(); s.setdefault("journal", []).append({"t": text.strip(), "mood": mood, "ts": time.time()}); _save(s)
    return "Günlüğüne yazdım."


def journal_read(days=7):
    s = _load(); now = time.time()
    es = [e for e in s.get("journal", []) if now - e["ts"] < float(days) * 86400]
    return [{"tarih": time.strftime("%d.%m %H:%M", time.localtime(e["ts"])), "yazı": e["t"], "ruh_hali": e.get("mood", "")} for e in es] or "Bu aralıkta günlük yazısı yok."


def journal_summary(days=7):
    es = journal_read(days)
    if isinstance(es, str):
        return es
    txt = "\n".join(f"{e['tarih']} [{e['ruh_hali']}] {e['yazı']}" for e in es)
    return _ask(f"Kullanıcının son {days} günlük günlük yazıları aşağıda. Nazik, kısa (5-6 cümle) bir haftalık değerlendirme yaz: öne çıkanlar, "
                "tekrar eden temalar, ruh hali eğilimi ve bir küçük öneri. Tanı koyma, yargılama.\n\n" + txt)


# ================= BİTKİ DOKTORU =================
PLANT_PROMPT = ("Bu bir bitki fotoğrafı. Türkçe JSON ver: {\"bitki\": \"yaygın adı (ve latince)\", \"emin\": true/false, \"sağlık\": \"iyi | dikkat | sorunlu\", "
                "\"sorunlar\": [\"görünen sorunlar (sararma, kahverengi uç, zararlı vb.)\"], \"neden\": \"olası nedenler\", \"yapılacaklar\": [\"...\"], "
                "\"sulama_gün\": tam sayı (kaç günde bir), \"ışık\": \"...\", \"ipucu\": \"...\"}. Bitki değilse {\"bitki\": \"\"}. Emin değilsen emin=false. Yalnızca JSON.")


def plant_analyze(img):
    d = _obj(llm.vision(PLANT_PROMPT, img, "image/jpeg", light=True))
    return d or {"bitki": "", "hata": "Analiz edilemedi"}


def plant_reminder(name, every_days=7):
    """Sulama hatırlatıcısı: her N günde bir bildirim (Telegram'a da gider)."""
    every = max(1, min(60, int(every_days or 7)))
    with _lock:
        s = _load(); ps = s.setdefault("plants", [])
        p = next((x for x in ps if x["name"].lower() == name.lower()), None)
        if p:
            p["every"] = every
        else:
            ps.append({"name": name, "every": every, "last": time.time()})
        _save(s)
    return f"Tamam: {name} için {every} günde bir sulama hatırlatacağım."


def plant_watered(name):
    with _lock:
        s = _load()
        for p in s.get("plants", []):
            if name.lower() in p["name"].lower():
                p["last"] = time.time(); _save(s); return f"{p['name']} sulandı olarak işaretlendi; {p['every']} gün sonra hatırlatırım."
    return f"'{name}' bitki listesinde yok."


def plant_list():
    s = _load(); now = time.time()
    return [{"bitki": p["name"], "her_gün": p["every"], "sonraki": max(0, round(p["every"] - (now - p["last"]) / 86400, 1))} for p in s.get("plants", [])] or "Kayıtlı bitki yok."


def plant_doctor():
    return {"ui": "scan", "mode": "plant", "not": "Bitki doktoru: bitkiyi kameraya göster; tür, sağlık durumu ve bakım çıkacak."}


# ================= HABER SAHNELERİ ("aydınlat beni") =================
def news_show(topic=""):
    """Haberleri sahne sahne anlatır: ekranda büyük başlık/sayı, kaynaklar; her sahne sesli okunur."""
    from .daily import news
    items = news(topic, limit=14)
    if not isinstance(items, list) or not items:
        return "Haber alınamadı (internet?)."
    heads = "\n".join(f"- {i.get('başlık') or i.get('title')} ({i.get('kaynak') or i.get('source', '')}, {i.get('tarih') or i.get('date', '')})" for i in items)
    prompt = ("Aşağıdaki GÜNCEL haber başlıklarından 5-7 sahnelik sesli bir gündem brifingi hazırla. Türkçe JSON: "
              '{"giriş": "1 cümle", "sahneler": [{"başlık": "kısa", "anlatım": "1-2 sesli cümle", "büyük": "öne çıkan sayı ya da tek kelime (başlıkta yoksa boş)", '
              '"etiket": "ekonomi|siyaset|dünya|spor|teknoloji|bilim|yaşam|diğer", "kaynaklar": ["..."]}], "kapanış": "1 cümle"}. '
              "YALNIZCA verilen başlıklardaki bilgiyi kullan; sayı ve isim uydurma. Aynı konudaki başlıkları birleştir.\n\n" + heads)
    d = _obj(_ask(prompt, light=False))
    sc = [x for x in d.get("sahneler") or [] if isinstance(x, dict) and x.get("anlatım")]
    if not sc:
        sc = [{"başlık": i.get("başlık") or i.get("title", ""), "anlatım": i.get("başlık") or i.get("title", ""), "büyük": "", "etiket": "", "kaynaklar": [i.get("kaynak", "")]} for i in items[:6]]
    return {"ui": "newsshow", "topic": topic, "giriş": d.get("giriş", "Gündemi özetliyorum."), "sahneler": sc[:8], "kapanış": d.get("kapanış", ""),
            "not": "Sahneler ekranda ve sesli anlatılıyor. Sen yalnızca 'Aydınlatıyorum efendim.' gibi TEK kısa cümle söyle, haberleri tekrar etme."}


# ================= AR OYUNLARI =================
def ar_game(kind="rps"):
    k = {"taş kağıt makas": "rps", "taş": "rps", "balon": "balloons", "balon patlatma": "balloons"}.get((kind or "").lower(), kind or "rps")
    return {"ui": "handfx", "action": "game", "game": k,
            "not": {"rps": "Taş-kağıt-makas: 3-2-1 sayımında elini göster (✊ taş, ✋ kağıt, ✌ makas).", "balloons": "Balon patlatma: 30 saniye, işaret parmağınla patlat."}.get(k, "")}


def game_score(game, score):
    with _lock:
        s = _load(); g = s.setdefault("games", {}).setdefault(game, {"best": 0, "plays": 0})
        g["plays"] += 1; best = score > g["best"]; g["best"] = max(g["best"], score); _save(s)
    return {"rekor": g["best"], "yeni_rekor": best, "oyun": g["plays"]}


# ================= zamanlayıcı =================
_last_tick = [0]


def tick(notify):
    """Dakikada bir: sulama zamanı gelen bitkiler (gün içinde 09-21 arası, bitki başına günde bir)."""
    now = time.time()
    if now - _last_tick[0] < 60:
        return
    _last_tick[0] = now
    h = time.localtime().tm_hour
    if not 9 <= h <= 21:
        return
    with _lock:
        s = _load(); changed = False
        for p in s.get("plants", []):
            due = now - p["last"] >= p["every"] * 86400
            if due and now - p.get("warned", 0) > 20 * 3600:
                p["warned"] = now; changed = True
                notify(f"🌱 {p['name']} için sulama zamanı. Suladıysan '{p['name']} suladım' de.", "reminder")
        if changed:
            _save(s)


GROUP = "life"
TOOLS = {
    "meeting_mode": (meeting_mode, _schema("Toplantı asistanı: canlı altyazı + döküm; bitince özet, kararlar, yapılacaklar (kaydeder, yapılacaklara ekler).",
                                           {"action": S("start | stop"), "title": S("toplantı adı")}), False),
    "focus_mode": (focus_mode, _schema("Odak modu (pomodoro): N dakika çalışma, bildirimler susar, sonra mola.", {"minutes": N("dakika"), "task": S("ne üzerinde"), "breaks": N("mola dk")}), False),
    "focus_stats": (focus_stats, _schema("Odak istatistikleri: bugün/bu hafta kaç dakika, kaç oturum."), False),
    "journal_add": (journal_add, _schema("Günlüğe yazar ('günlüğüme yaz: …').", {"text": S("yazı"), "mood": S("ruh hali")}, ["text"]), False),
    "journal_read": (journal_read, _schema("Son N günün günlük yazıları.", {"days": N("gün")}), False),
    "journal_summary": (journal_summary, _schema("Günlükten haftalık değerlendirme ('bu hafta nasıldım').", {"days": N("gün")}), False),
    "plant_doctor": (plant_doctor, _schema("Bitki doktoru: kameradaki bitkiyi tanır, sağlığını ve bakımını söyler."), False),
    "plant_reminder": (plant_reminder, _schema("Bitki sulama hatırlatıcısı (her N günde bir).", {"name": S("bitki"), "every_days": N("gün")}, ["name"]), False),
    "plant_watered": (plant_watered, _schema("Bitki sulandı ('monsterayı suladım').", {"name": S("bitki")}, ["name"]), False),
    "plant_list": (plant_list, _schema("Kayıtlı bitkiler ve sonraki sulama."), False),
    "news_show": (news_show, _schema("'AYDINLAT BENİ': güncel haberleri ekranda sahne sahne, sesli anlatır.", {"topic": S("konu (boş = genel gündem)")}), False),
    "ar_game": (ar_game, _schema("AR oyunu: taş-kağıt-makas (rps) ya da balon patlatma (balloons).", {"kind": S("rps | balloons")}), False),
}
