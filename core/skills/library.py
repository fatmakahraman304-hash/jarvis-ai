"""KİTAPLIK: kitaplarını tanı, notlarını ve okuma durumunu tut, AR'de raftan kitap çek.

- Raf taraması (kameradan tek kare): görüntü örtüşen parçalara bölünür, her parça Gemini'ye (hafif model) gönderilir;
  model yalnızca sırtta GERÇEKTEN okuduğu adı yazar, okuyamadığı sırt 'belirsiz' kalır. Kutular kameraya göre kaydedilir
  (AR'de işaret parmağıyla seçmek için). Elle düzelttiğin adlar yeniden taramada ezilmez; notlar korunur.
- Raf fotoğrafından ekleme: telefonla yakından çekilen fotoğraftaki kitaplar kalıcı olarak eklenir (yer bilgisi olmadan).
- Kitap defteri: adı bilinen kitap için JARVIS özet, ana fikirler, yazar, temalar, neden okumalı ve SENİN rafından benzer kitaplar yazar.
  Kitabı tanımıyorsa uydurmaz; kitaptan birebir alıntı üretmez (alıntılar yalnızca seninkiler).
"""
import io
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import uuid

from .. import llm
from ..config import DATA
from ..tools import N, S, _schema

FILE = DATA / "kitaplik.json"
_lock = threading.Lock()
STATUSES = {"okunacak", "okunuyor", "bitti"}


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"books": [], "shelf": {}}


def _save(d):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def _key(s):
    s = (s or "").lower()
    for a, b in (("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c"), ("â", "a"), ("î", "i")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", s)


def _find(d, title):
    k = _key(title)
    if not k:
        return None
    for b in d["books"]:
        if _key(b.get("title")) == k:
            return b
    for b in d["books"]:  # kısmi eşleşme ("Mülksüzler" ↔ "Mülksüzler: Bir Ütopya")
        bk = _key(b.get("title"))
        if bk and len(k) >= 4 and (k in bk or bk in k):
            return b
    return None


def _new(title="", author="", box=None, source="elle"):
    return {"id": uuid.uuid4().hex[:10], "title": title.strip(), "author": (author or "").strip(), "box": box, "status": "okunacak",
            "page": 0, "notes": [], "quotes": [], "summary": "", "notebook": None, "cover": "", "manual": source == "elle",
            "source": source, "added": time.strftime("%Y-%m-%d")}


# ---------------- görüntüden kitap okuma ----------------
PROMPT = ("Bu görüntü bir kitaplık rafının parçası. Görünen HER kitap sırtı için JSON listesi döndür: "
          '[{"title": "...", "author": "...", "box": [x0, y0, x1, y1]}]. box: bu görüntüye göre 0-1000 arası koordinatlar (sırtın tamamı). '
          "Kurallar: title ve author'a YALNIZCA sırtta gerçekten okuyabildiğin yazıyı yaz; tahmin etme, uydurma. Okuyamadığın sırt için "
          'title "" bırak (yine de kutusunu ver). Kitap yoksa []. Sadece JSON yaz, açıklama yazma.')


def _parse(txt):
    m = re.search(r"\[.*\]", txt or "", re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for it in arr if isinstance(arr, list) else []:
        if not isinstance(it, dict):
            continue
        box = it.get("box")
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
            box = None
        else:
            x0, y0, x1, y1 = [max(0.0, min(1000.0, float(v))) for v in box]
            if x1 - x0 < 3 or y1 - y0 < 3:
                box = None
            else:
                box = [min(x0, x1) / 1000, min(y0, y1) / 1000, max(x0, x1) / 1000, max(y0, y1) / 1000]
        title = str(it.get("title") or "").strip()
        if title.lower() in ("belirsiz", "okunamadı", "unknown", "?"):
            title = ""
        out.append({"title": title[:160], "author": str(it.get("author") or "").strip()[:100], "box": box})
    return out


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0


def _tiles(img_bytes, region=None, cols=3, rows=2, overlap=0.15):
    """Görüntüyü örtüşen parçalara böler (küçük sırtlar büyüyünce çok daha fazlası okunur). Pillow yoksa tek parça."""
    try:
        from PIL import Image
    except ImportError:
        return [((0, 0, 1, 1), img_bytes)]
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    W, H = im.size
    rx0, ry0, rx1, ry1 = region or (0, 0, 1, 1)
    out = []
    tw, th = (rx1 - rx0) / cols, (ry1 - ry0) / rows
    for r in range(rows):
        for c in range(cols):
            x0 = max(0, rx0 + c * tw - tw * overlap); x1 = min(1, rx0 + (c + 1) * tw + tw * overlap)
            y0 = max(0, ry0 + r * th - th * overlap); y1 = min(1, ry0 + (r + 1) * th + th * overlap)
            crop = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
            if crop.width < 1100:  # büyüt: model küçük yazıyı daha iyi okur
                k = 1100 / max(1, crop.width)
                crop = crop.resize((int(crop.width * k), int(crop.height * k)))
            buf = io.BytesIO(); crop.save(buf, "JPEG", quality=88)
            out.append(((x0, y0, x1, y1), buf.getvalue()))
    return out


def detect(img_bytes, region=None, tiles=True):
    """Görüntüdeki kitapları bulur: [{title, author, box (tam görüntüye göre 0-1)}]."""
    parts = _tiles(img_bytes, region) if tiles else [((0, 0, 1, 1), img_bytes)]
    found = []
    from concurrent.futures import ThreadPoolExecutor
    def one(p):
        (x0, y0, x1, y1), data = p
        try:
            items = _parse(llm.vision(PROMPT, data, "image/jpeg", light=True))
        except Exception as e:
            print("[kitaplık] parça okunamadı:", str(e)[:120])
            return []
        for it in items:
            if it["box"]:
                bx = it["box"]
                it["box"] = [x0 + bx[0] * (x1 - x0), y0 + bx[1] * (y1 - y0), x0 + bx[2] * (x1 - x0), y0 + bx[3] * (y1 - y0)]
        return items
    with ThreadPoolExecutor(max_workers=3) as ex:
        for items in ex.map(one, parts):
            found += items
    merged = []  # örtüşen parçalardaki aynı kitabı birleştir
    for it in sorted(found, key=lambda x: -len(x["title"])):
        dup = None
        for m in merged:
            if it["box"] and m["box"] and _iou(it["box"], m["box"]) > 0.35:
                dup = m; break
            if it["title"] and _key(it["title"]) == _key(m["title"]):
                dup = m; break
        if dup:
            if not dup["title"] and it["title"]:
                dup.update(title=it["title"], author=it["author"])
            continue
        merged.append(it)
    return merged


def scan_shelf(img_bytes, w=0, h=0):
    """Kameradan raf taraması: kutular kaydedilir (AR'de seçim için)."""
    with _lock:
        d = _load()
        prev_region = (d.get("shelf") or {}).get("region")
    items = detect(img_bytes, region=prev_region)
    with _lock:
        d = _load()
        boxed = [b for b in d["books"] if b.get("box")]
        added = named = 0
        for it in items:
            if not it["box"]:
                continue
            match = next((b for b in boxed if _iou(b["box"], it["box"]) > 0.4), None) or (_find(d, it["title"]) if it["title"] else None)
            if match:
                match["box"] = it["box"]
                if it["title"] and not match.get("manual") and not match.get("title"):
                    match.update(title=it["title"], author=it["author"] or match.get("author", ""))
                continue
            b = _new(it["title"], it["author"], it["box"], "tarama")
            d["books"].append(b); added += 1
        named = sum(1 for b in d["books"] if b.get("box") and b.get("title"))
        unknown = sum(1 for b in d["books"] if b.get("box") and not b.get("title"))
        boxes = [b["box"] for b in d["books"] if b.get("box")]
        if boxes:  # sonraki tarama yalnızca raf bölgesine odaklansın (sırtlar daha büyük görünür)
            region = [max(0, min(x[0] for x in boxes) - 0.03), max(0, min(x[1] for x in boxes) - 0.03),
                      min(1, max(x[2] for x in boxes) + 0.03), min(1, max(x[3] for x in boxes) + 0.03)]
            d["shelf"] = {"region": region, "w": w, "h": h, "ts": time.time()}
        _save(d)
    return {"tanınan": named, "belirsiz": unknown, "yeni": added, "özet": f"{named} kitap tanındı · {unknown} belirsiz"}


def add_from_photo(img_bytes):
    """Yakından çekilmiş raf fotoğrafından kitapları kalıcı olarak ekler (yer bilgisi olmadan)."""
    items = [i for i in detect(img_bytes, tiles=True) if i["title"]]
    added = []
    with _lock:
        d = _load()
        for it in items:
            if _find(d, it["title"]):
                continue
            b = _new(it["title"], it["author"], None, "fotoğraf"); d["books"].append(b); added.append(b["title"])
        _save(d)
    for t in added[:12]:
        threading.Thread(target=_bg_fill, args=(t,), daemon=True).start()
    return {"eklenen": added, "okunan": len(items)}


# ---------------- kapak + kitap defteri ----------------
def _cover(title, author=""):
    try:
        q = urllib.parse.urlencode({"title": title, "author": author, "limit": 1, "fields": "cover_i,key"} if author else {"title": title, "limit": 1, "fields": "cover_i,key"})
        req = urllib.request.Request("https://openlibrary.org/search.json?" + q, headers={"User-Agent": "JARVIS-kitaplik"})
        with urllib.request.urlopen(req, timeout=8) as r:
            docs = json.loads(r.read()).get("docs") or []
        if docs and docs[0].get("cover_i"):
            return f"https://covers.openlibrary.org/b/id/{docs[0]['cover_i']}-M.jpg"
    except Exception:
        pass
    return ""


def book_fill(title, force=False):
    """Kitap defterini doldurur (özet, ana fikirler, yazar, temalar, neden okumalı, benzer kitaplar)."""
    with _lock:
        d = _load(); b = _find(d, title)
        if not b:
            return f"'{title}' kitaplığında yok."
        if b.get("notebook") and not force:
            return {"kitap": b["title"], "defter": b["notebook"], "özet": b["summary"]}
        mine = [x["title"] for x in d["books"] if x.get("title") and x["id"] != b["id"]][:120]
    from .. import brain
    prompt = (f"Kitap: '{b['title']}'" + (f", yazar: {b['author']}" if b.get("author") else "") + ".\n"
              f"Kullanıcının kitaplığındaki diğer kitaplar: {', '.join(mine) or '(yok)'}\n"
              "Bu kitabı gerçekten tanıyorsan Türkçe JSON yaz: {\"bilinen\": true, \"yazar_tam\": \"...\", \"ozet\": \"3 cümle\", "
              "\"ana_fikirler\": [\"4-6 madde\"], \"yazar_hakkinda\": \"2 cümle\", \"temalar\": [\"...\"], \"neden_okumali\": \"...\", "
              "\"kime_uygun\": \"...\", \"benzer\": [\"YALNIZCA yukarıdaki listeden en fazla 4 kitap\"]}. "
              "Kitabı tanımıyorsan ya da emin değilsen sadece {\"bilinen\": false} yaz. Kitaptan birebir alıntı yazma. Yalnızca JSON.")
    try:
        txt = brain.ask(prompt, light=False)
        m = re.search(r"\{.*\}", txt, re.S)
        nb = json.loads(m.group(0)) if m else {"bilinen": False}
    except Exception as e:
        return f"Defter yazılamadı: {e}"
    cover = b.get("cover") or _cover(b["title"], b.get("author", ""))
    with _lock:
        d = _load(); b2 = next((x for x in d["books"] if x["id"] == b["id"]), None)
        if not b2:
            return "Kitap silinmiş."
        if nb.get("bilinen"):
            mine_keys = {_key(t) for t in mine}
            nb["benzer"] = [t for t in (nb.get("benzer") or []) if _key(t) in mine_keys][:4]
            b2["summary"] = nb.get("ozet", "")
            if not b2.get("author") and nb.get("yazar_tam"):
                b2["author"] = nb["yazar_tam"]
        b2["notebook"] = nb
        b2["cover"] = cover
        _save(d)
    return {"kitap": b2["title"], "defter": nb if nb.get("bilinen") else "JARVIS bu kitabı tanımıyor; sayfa uydurulmadı.", "kapak": cover}


def _bg_fill(title):
    try:
        book_fill(title)
    except Exception as e:
        print("[kitaplık] defter:", e)


# ---------------- araçlar ----------------
def book_list(status=""):
    d = _load()
    books = [b for b in d["books"] if b.get("title") and (not status or b.get("status") == status)]
    if not books:
        return "Kitaplık boş. 'kitaplığımı tara' de ya da Ayarlar > KİTAPLIK'tan fotoğrafla ekle."
    return [{"ad": b["title"], "yazar": b.get("author", ""), "durum": b.get("status"), "sayfa": b.get("page") or None,
             "not_sayısı": len(b.get("notes") or [])} for b in books]


def book_add(title, author=""):
    with _lock:
        d = _load()
        if _find(d, title):
            return f"'{title}' zaten kitaplığında."
        b = _new(title, author); d["books"].append(b); _save(d)
    threading.Thread(target=_bg_fill, args=(b["title"],), daemon=True).start()
    return f"Tamamdır, '{b['title']}' kitaplığına eklendi; sayfalarını birazdan dolduruyorum."


def book_update(title, status="", page=0, note="", quote="", new_title=""):
    """Durum (okunacak/okunuyor/bitti), sayfa, not, alıntı ekler. Kitap yoksa ekler."""
    created = False
    with _lock:
        d = _load(); b = _find(d, title)
        if not b:
            b = _new(title); d["books"].append(b); created = True
        st = (status or "").lower()
        st = {"bitirdim": "bitti", "okudum": "bitti", "okuyorum": "okunuyor", "başladım": "okunuyor"}.get(st, st)
        if st in STATUSES:
            b["status"] = st
        if page:
            b["page"] = int(page); b["status"] = b["status"] if st else "okunuyor"
        if note:
            b.setdefault("notes", []).append({"t": note.strip(), "d": time.strftime("%Y-%m-%d")})
        if quote:
            b.setdefault("quotes", []).append({"t": quote.strip(), "d": time.strftime("%Y-%m-%d")})
        if new_title:
            b["title"] = new_title.strip(); b["manual"] = True
        _save(d)
    if created or new_title:
        threading.Thread(target=_bg_fill, args=(b["title"],), daemon=True).start()
    return f"'{b['title']}' güncellendi" + (" (kitaplığa da eklendi)" if created else "") + "."


def book_suggest(mood=""):
    d = _load()
    pool = [b for b in d["books"] if b.get("title") and b.get("status") != "bitti"]
    if not pool:
        return "Rafında okunmamış kitap yok."
    return {"aday_kitaplar": [{"ad": b["title"], "yazar": b.get("author", ""), "özet": b.get("summary", "")} for b in pool[:40]],
            "not": "YALNIZCA bu listeden öner; listede olmayan kitap önerme." + (f" Kullanıcının isteği: {mood}" if mood else "")}


def shelf_scan():
    return {"ui": "library", "action": "scan", "not": "Kamera açılıyor; raf taraması 20-30 sn sürer."}


def book_name_open(title):
    """AR'de açık olan (adı okunamamış) kitaba ad verir: 'bu kitabın adı …'"""
    return {"ui": "library", "action": "name_open", "title": title}


# ---------------- arayüz API'si ----------------
def api_get():
    d = _load()
    return {"books": d["books"], "shelf": d.get("shelf") or {}}


def api_save_book(b):
    with _lock:
        d = _load()
        cur = next((x for x in d["books"] if x["id"] == b.get("id")), None)
        if not cur:
            cur = _new(b.get("title", ""), b.get("author", ""), b.get("box")); d["books"].append(cur)
        for k in ("title", "author", "status", "page", "notes", "quotes", "summary", "box", "cover"):
            if k in b:
                cur[k] = b[k]
        if "title" in b:
            cur["manual"] = True
        _save(d)
    if cur.get("title") and not cur.get("notebook"):
        threading.Thread(target=_bg_fill, args=(cur["title"],), daemon=True).start()
    return cur


def api_delete(bid):
    with _lock:
        d = _load(); d["books"] = [b for b in d["books"] if b["id"] != bid]; _save(d)
    return {"ok": True}


GROUP = "library"
TOOLS = {
    "book_list": (book_list, _schema("Kullanıcının kitaplığındaki kitapları listeler (durum filtresi: okunacak/okunuyor/bitti).", {"status": S("durum")}), False),
    "book_add": (book_add, _schema("Kitaplığa kitap ekler ('kitaplığıma X'i ekle').", {"title": S("kitap adı"), "author": S("yazar")}, ["title"]), False),
    "book_update": (book_update, _schema("Kitaba not/alıntı ekler, durum (okunacak/okunuyor/bitti) ya da sayfa günceller. 'X'i bitirdim', 'Y'de 120. sayfadayım', 'Z'ye not ekle: …'.",
                                               {"title": S("kitap adı"), "status": S("okunacak | okunuyor | bitti"), "page": N("sayfa"), "note": S("not"), "quote": S("alıntı"),
                                                "new_title": S("yeni ad")}, ["title"]), False),
    "book_fill": (book_fill, _schema("Kitabın defterini doldurur (özet, ana fikirler, yazar, temalar, benzer kitaplar).", {"title": S("kitap adı"), "force": {"type": "boolean"}}, ["title"]), False),
    "book_suggest": (book_suggest, _schema("Kullanıcının KENDİ rafından okunacak kitap önerir.", {"mood": S("istek/ruh hali")}), False),
    "shelf_scan": (shelf_scan, _schema("Kameradan kitaplığı tarar (raftaki kitapları tanır)."), False),
    "book_name_open": (book_name_open, _schema("AR'de açık kitaba ad verir ('bu kitabın adı X').", {"title": S("ad")}, ["title"]), False),
}
