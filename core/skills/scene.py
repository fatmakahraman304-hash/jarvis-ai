"""SAHNE: odayı tara → nesneler kutulanır → tıklayınca hologram olarak öne gelir (bilgi, nerede satılır, yerini hatırla).
Nesne hafızası ("kumandayı nerede bıraktım?"), canlı nesne bulucu, belge tarayıcı (yazıyı çıkar/çevir/özetle/kaydet),
QR okuyucu, havaya çizim ("ne çizdim?"), egzersiz sayacı, duruş/göz molası, ruh hali. Görüntü işleme mümkün olduğunca
tarayıcıda (MediaPipe) yapılır; Gemini'ye yalnızca sen istediğinde TEK kare gider."""
import json
import re
import threading
import time

from .. import llm
from ..config import DATA
from ..tools import S, _schema

MEM = DATA / "nesne_hafizasi.json"
_lock = threading.Lock()


def _json(txt, kind="list"):
    m = re.search(r"\[.*\]" if kind == "list" else r"\{.*\}", txt or "", re.S)
    if not m:
        return [] if kind == "list" else {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return [] if kind == "list" else {}


# ---------------- oda taraması ----------------
SCAN_PROMPT = ("Bu bir oda/ortam görüntüsü. Görünen belirgin nesneleri (en fazla 25) JSON listesi olarak ver: "
               '[{"ad": "Türkçe kısa ad", "tür": "mobilya|elektronik|bitki|kitap|mutfak|giyim|dekor|diğer", "box": [x0,y0,x1,y1], "not": "çok kısa ayırt edici özellik (renk/marka)"}]. '
               "box: 0-1000 arası, görüntüye göre. Sadece GERÇEKTEN gördüklerini yaz; insanları 'kişi' olarak işaretle, kim olduklarını tahmin etme. Yalnızca JSON.")


def analyze_room(img, location=""):
    items = []
    for it in _json(llm.vision(SCAN_PROMPT, img, "image/jpeg", light=True)):
        if not isinstance(it, dict) or not it.get("ad"):
            continue
        b = it.get("box")
        if isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
            x0, y0, x1, y1 = [max(0, min(1000, float(v))) / 1000 for v in b]
            b = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            if b[2] - b[0] < 0.01 or b[3] - b[1] < 0.01:
                continue
        else:
            continue
        items.append({"ad": str(it["ad"])[:40], "tür": str(it.get("tür", "diğer"))[:20], "box": b, "not": str(it.get("not", ""))[:80]})
    remember_scene(items, location)
    notes = _notes()
    for it in items:  # nesneye bırakılmış yapışkan notlar (hologram etiket olarak görünür)
        n = _match_notes(notes, it["ad"])
        if n:
            it["notlar"] = n
    return {"nesneler": items, "konum": location}


# ---------------- nesnelere yapışkan not ----------------
NOTES = DATA / "nesne_notlari.json"


def _notes():
    try:
        return json.loads(NOTES.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _stem(w):
    w = (w or "").lower().strip()
    for suf in ("ının", "inin", "unun", "ünün", "ına", "ine", "una", "üne", "nın", "nin", "ya", "ye", "na", "ne", "yı", "yi", "yu", "yü", "a", "e", "ı", "i", "u", "ü"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _match_notes(notes, name):
    k = _stem(name)
    return [n for key, lst in notes.items() for n in lst if k and (key in k or k in key)]


def object_note(thing, text="", action="add"):
    """Nesneye sanal yapışkan not bırakır: 'buzdolabına not bırak: süt al'. Tarama/kamerada nesne görünce not hologram olarak çıkar."""
    key = _stem(thing)
    with _lock:
        notes = _notes()
        if action in ("sil", "delete", "clear", "temizle"):
            notes.pop(key, None); msg = f"{thing} üzerindeki notlar silindi."
        elif action in ("list", "liste", "oku"):
            return _match_notes(notes, thing) or f"{thing} üzerinde not yok."
        else:
            notes.setdefault(key, []).append({"t": text.strip(), "ts": time.time()}); msg = f"📌 Not {thing} üzerine bırakıldı: '{text.strip()}'. Kamera onu görünce göstereceğim."
        NOTES.parent.mkdir(parents=True, exist_ok=True)
        NOTES.write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    return msg


def object_notes_all():
    return {k: [n["t"] for n in v] for k, v in _notes().items()} or "Hiçbir nesnede not yok."


def remember_scene(items, location=""):
    """Nesne hafızası: her taramada nesnelerin son görüldüğü yer/zaman saklanır ("X nerede?")."""
    if not items:
        return
    with _lock:
        try:
            mem = json.loads(MEM.read_text(encoding="utf-8"))
        except Exception:
            mem = {}
        now = time.time()
        for it in items:
            k = it["ad"].lower()
            pos = it["box"]
            cx, cy = (pos[0] + pos[2]) / 2, (pos[1] + pos[3]) / 2
            where = ("sol" if cx < 0.4 else "sağ" if cx > 0.6 else "orta") + " " + ("üst" if cy < 0.4 else "alt" if cy > 0.6 else "")
            mem[k] = {"ad": it["ad"], "konum": location or mem.get(k, {}).get("konum", ""), "görüntüde": where.strip(), "not": it.get("not", ""), "ts": now}
        MEM.parent.mkdir(parents=True, exist_ok=True)
        MEM.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")


def where_is(thing):
    """Nesne hafızasından: 'kumandayı nerede bıraktım?'"""
    try:
        mem = json.loads(MEM.read_text(encoding="utf-8"))
    except Exception:
        mem = {}
    q = (thing or "").lower().strip()
    stem = q[:-2] if len(q) > 5 and q.endswith(("yı", "yi", "yu", "yü", "ı", "i", "u", "ü", "ni", "nı")) else q
    hits = [v for k, v in mem.items() if stem and (stem in k or k in q)]
    if not hits:
        return {"bulunamadı": thing, "not": "Hafızamda yok. 'odayı tara' ya da 'kumandayı bul' (canlı arama) diyebilirsin."}
    hits.sort(key=lambda v: -v["ts"])
    v = hits[0]
    ago = int((time.time() - v["ts"]) / 60)
    return {"nesne": v["ad"], "son_görüldüğü": (v.get("konum") or "son taramada") + (f", görüntünün {v['görüntüde']} kısmında" if v.get("görüntüde") else ""),
            "ne_zaman": "az önce" if ago < 2 else f"{ago} dakika önce" if ago < 120 else time.strftime("%d.%m %H:%M", time.localtime(v["ts"])), "not": v.get("not", "")}


def describe_object(img, name="", question=""):
    """Tıklanan nesnenin kırpılmış görüntüsü → hologram bilgi kartı."""
    p = (f"Bu kırpılmış görüntüde muhtemelen '{name}' var. " if name else "") + (question or
         "Bu nesne nedir? Türkçe JSON ver: {\"ad\": \"...\", \"ne\": \"1-2 cümle ne olduğu/ne işe yaradığı\", \"marka_model\": \"görünüyorsa, yoksa boş\", "
         "\"tahmini_boyut\": \"kabaca\", \"ipucu\": \"bakım/kullanım için kısa ipucu\", \"arama\": \"satın almak için arama ifadesi\"}. Emin olmadığını uydurma. Yalnızca JSON.")
    txt = llm.vision(p, img, "image/jpeg", light=True)
    d = _json(txt, "obj") if not question else {"cevap": txt}
    return d or {"ne": txt[:400]}


# ---------------- belge / çizim ----------------
def analyze_doc(img, mode="text", lang="tr"):
    prompts = {
        "text": "Bu görüntüdeki yazıyı olduğu gibi, satır düzenini koruyarak yaz. Başka bir şey ekleme.",
        "summary": "Bu belgedeki yazıyı oku ve Türkçe 4-6 maddelik özet çıkar; önemli tarih/tutar/isimleri belirt.",
        "translate": f"Bu görüntüdeki yazıyı {'Türkçe' if lang == 'tr' else lang} diline çevir; yalnızca çeviriyi yaz.",
        "math": "Bu görüntüdeki soruyu/problemi oku ve adım adım Türkçe çöz.",
    }
    return {"metin": llm.vision(prompts.get(mode, prompts["text"]), img, "image/jpeg", light=mode == "text")}


def save_text(text, name=""):
    from ..tools import _path
    d = _path("belgeler") / "JARVIS taramaları"
    d.mkdir(parents=True, exist_ok=True)
    f = d / ((re.sub(r"[^\w\- ]+", "", name).strip() or time.strftime("tarama_%Y%m%d_%H%M%S")) + ".txt")
    f.write_text(text, encoding="utf-8")
    return str(f)


def analyze_drawing(img):
    return {"cevap": llm.vision("Bu, kullanıcının havada parmağıyla çizdiği basit bir çizim (siyah zemin üstünde ışık çizgisi). Ne çizmiş? "
                                "Kısa, eğlenceli, sesli okunacak Türkçe bir cümleyle söyle; harf/rakam/şekil ise onu söyle.", img, "image/png", light=True)}


# ---------------- avuçta HUD verisi ----------------
_palm = {"ts": 0, "data": {}}


def palm_info():
    """Avuç HUD'u için: hava (10 dk önbellek), sıradaki etkinlik, sistem."""
    now = time.time()
    if now - _palm["ts"] < 300 and _palm["data"]:
        d = dict(_palm["data"])
    else:
        d = {}
        try:
            from ..config import load_settings
            from ..tools import weather
            w = weather(load_settings().get("city") or "Istanbul")
            if isinstance(w, dict):
                d["hava"] = f"{w.get('şehir', '')} {w.get('sıcaklık', '')} · {w.get('durum', '')}"
        except Exception:
            pass
        try:
            from . import google
            if google.connected():
                ev = google.calendar_events(days=1)
                if isinstance(ev, list) and ev:
                    e = ev[0]
                    st = str(e.get("başlangıç") or "")
                    d["etkinlik"] = (st[11:16] if "T" in st else "bugün") + " " + (e.get("başlık") or "")
        except Exception:
            pass
        _palm.update(ts=now, data=d)
    try:
        import psutil
        d["sistem"] = f"CPU %{psutil.cpu_percent():.0f} · RAM %{psutil.virtual_memory().percent:.0f}"
    except Exception:
        pass
    return d


# ---------------- araçlar (arayüz komutları) ----------------
def room_scan(location=""):
    return {"ui": "scan", "mode": "room", "location": location, "not": "Kamera açılıyor; oda taranıp nesneler işaretlenecek. Kullanıcı bir nesneye tıklayınca hologram olarak öne gelir."}


def find_object(thing):
    w = where_is(thing)
    return {"ui": "scan", "mode": "find", "thing": thing, "hafıza": w,
            "not": "Canlı arama başladı: kamera nesneyi görünce işaretleyip ses çıkaracak. Hafızadaki son konumu da söyle."}


def doc_scan(mode="text"):
    m = {"özet": "summary", "çeviri": "translate", "çevir": "translate", "yazı": "text", "metin": "text", "soru": "math", "çöz": "math"}.get((mode or "").lower(), mode or "text")
    return {"ui": "scan", "mode": "doc", "doc": m, "not": "Belge tarayıcı açıldı: belgeyi kameraya göster."}


def qr_scan():
    return {"ui": "scan", "mode": "qr", "not": "QR/barkod okuyucu açıldı."}


def color_pick():
    return {"ui": "scan", "mode": "color", "not": "Renk seçici: görüntüde bir yere tıkla ya da AR'de işaret parmağınla göster."}


def body_mode(kind="posture", target=0):
    k = {"duruş": "posture", "oturuş": "posture", "göz": "posture", "squat": "squat", "çömelme": "squat", "şınav": "pushup", "zıplama": "jumping",
         "ruh hali": "mood", "duygu": "mood", "kapat": "off"}.get((kind or "").lower(), kind or "posture")
    return {"ui": "body", "kind": k, "target": int(target or 0),
            "not": {"posture": "Duruş ve ekran mesafesi izleniyor; 20 dakikada bir göz molası hatırlatılacak.", "mood": "Ruh hali HUD'u açıldı.",
                    "off": "Vücut izleme kapatıldı."}.get(k, "Egzersiz sayacı açıldı; her tekrarı sesli sayacağım.")}


def ar_extra(kind="palm"):
    k = {"avuç": "palm", "çizim": "draw", "çiz": "draw", "maske": "mask", "iron man": "mask", "kask": "mask"}.get((kind or "").lower(), kind or "palm")
    return {"ui": "handfx", "action": "extra", "extra": k, "not": {"palm": "Avucunu kameraya aç: üstünde saat, hava ve sıradaki etkinlik belirir.",
                                                                    "draw": "Havaya çizim: işaret parmağınla çiz, ✌ ile 'ne çizdim?', ✊ ile sil.",
                                                                    "mask": "Iron Man kask HUD'u yüzüne yerleşti."}.get(k, "")}


GROUP = "scene"
TOOLS = {
    "room_scan": (room_scan, _schema("ODAYI TARA: kameradan odadaki nesneleri bulup işaretler; kullanıcı tıklayınca nesne hologram olarak öne gelir.", {"location": S("oda adı (salon, mutfak…)")}), False),
    "find_object": (find_object, _schema("Nesne bul: 'kumandayı bul', 'gözlüğüm nerede' — hafızadaki son konum + kamerada canlı arama.", {"thing": S("nesne")}, ["thing"]), False),
    "where_is": (where_is, _schema("Nesne hafızası: bir nesnenin en son görüldüğü yer ve zaman ('X'i nerede bıraktım').", {"thing": S("nesne")}, ["thing"]), False),
    "doc_scan": (doc_scan, _schema("Belge tarayıcı: kameradaki belgenin yazısını çıkarır / özetler / çevirir / sorusunu çözer.", {"mode": S("text | summary | translate | math")}), False),
    "object_note": (object_note, _schema("Nesneye sanal yapışkan not bırakır/okur/siler ('buzdolabına not bırak: süt al'); kamera nesneyi görünce not hologram olarak çıkar.",
                                         {"thing": S("nesne"), "text": S("not"), "action": S("add | list | delete")}, ["thing"]), False),
    "object_notes_all": (object_notes_all, _schema("Hangi nesnelerde not var."), False),
    "qr_scan": (qr_scan, _schema("QR kod / barkod okuyucu açar."), False),
    "color_pick": (color_pick, _schema("Kameradan renk seçici (renk adı ve kodu)."), False),
    "body_mode": (body_mode, _schema("Vücut: duruş/göz molası takibi, egzersiz sayacı (squat, şınav, zıplama), ruh hali HUD'u ya da kapat.",
                                     {"kind": S("posture | squat | pushup | jumping | mood | off"), "target": {"type": "integer", "description": "hedef tekrar"}}), False),
    "ar_extra": (ar_extra, _schema("AR ekstra: avuçta HUD (saat/hava/etkinlik), havaya çizim, Iron Man kask HUD'u.", {"kind": S("palm | draw | mask")}), False),
}
