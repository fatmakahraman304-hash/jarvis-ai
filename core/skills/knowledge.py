"""Bilgi merkezi: kişisel belge kütüphanesi (PDF/Word/TXT/MD/HTML/EPUB/web sayfası), parçalara bölüp BM25 + (varsa) vektör ile hibrit arama,
kaynak göstererek soru cevaplama, 3D bilgi/ilişki grafiği, sesli kitap (edge-tts mp3 bölümleri), quiz + aralıklı tekrar (Leitner) ve öğrenme planı."""
import asyncio
import html
import json
import math
import re
import threading
import time
import zipfile
from collections import Counter
from pathlib import Path

from .. import memory
from ..tools import HOME, S, _path, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS lib_docs(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, source TEXT UNIQUE, kind TEXT, pages INTEGER, chars INTEGER, added REAL, tags TEXT);
CREATE TABLE IF NOT EXISTS lib_chunks(id INTEGER PRIMARY KEY AUTOINCREMENT, doc INTEGER, n INTEGER, page INTEGER, text TEXT);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON lib_chunks(doc);
CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, q TEXT, options TEXT, answer INTEGER, explain TEXT,
    box INTEGER DEFAULT 1, due REAL, seen INTEGER DEFAULT 0, correct INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS learn_plans(id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, plan TEXT, created REAL);
""")
try:  # eski veritabanları için: parçanın sayfadaki başlangıç konumu
    memory._q("ALTER TABLE lib_chunks ADD COLUMN off INTEGER", commit=True)
except Exception:
    pass

STOP = set("""ve veya ile bir bu şu o da de ki mi mı mu mü için gibi daha çok en ama fakat ancak olarak olan olarak ise ya hem her
edildi edilen etti eder oldu olur olmuş olduğu yılında yılı kadar sonra önce arasında göre bunun şekilde sadece ayrıca ilgili üzerinde tarafından vardır değildir
the a an and or of to in on for is are was were be been with by as at from that this it its not but which into than then there their""".split())
CHUNK, OVER = 1100, 150
_idx_lock = threading.Lock()


# ---------------- metin çıkarma ----------------

def _pages_from(p):
    ext = p.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return [(pg.extract_text() or "") for pg in PdfReader(str(p)).pages]
    if ext == ".docx":
        import docx
        d = docx.Document(str(p))
        return ["\n".join(par.text for par in d.paragraphs)]
    if ext == ".epub":
        out = []
        with zipfile.ZipFile(p) as z:
            names = sorted(n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
            for n in names:
                out.append(_strip_html(z.read(n).decode("utf-8", "ignore")))
        return [x for x in out if x.strip()]
    if ext in (".html", ".htm"):
        return [_strip_html(p.read_text(encoding="utf-8", errors="ignore"))]
    if ext == ".pptx":
        from pptx import Presentation
        return ["\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) for s in Presentation(str(p)).slides]
    return [p.read_text(encoding="utf-8", errors="ignore")]


def _strip_html(t):
    t = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", html.unescape(t)).strip()


def _chunks(pages):
    out = []
    for pno, txt in enumerate(pages, 1):
        txt = re.sub(r"\s+\n", "\n", txt).strip()
        i = 0
        while i < len(txt):
            end = min(len(txt), i + CHUNK)
            if end < len(txt):  # cümle sonunda kes
                cut = max(txt.rfind(". ", i, end), txt.rfind("\n", i, end))
                if cut > i + CHUNK * 0.5:
                    end = cut + 1
            raw = txt[i:end]
            piece = raw.strip()
            if len(piece) > 15:
                out.append((pno, i + len(raw) - len(raw.lstrip()), piece))
            if end >= len(txt):
                break
            i = max(end - OVER, i + 1)
    return out


def _tok(t):
    t = t.lower().replace("İ", "i").replace("I", "ı")
    return [w[:7] for w in re.findall(r"[a-zçğıöşü0-9]{2,}", t) if w not in STOP]  # kaba Türkçe gövde: ilk 7 harf


# ---------------- kütüphane ----------------

def library_add(path, title="", tags=""):
    """Dosya, klasör (içindeki tüm belgeler) ya da http(s) web sayfası ekler."""
    src = str(path).strip()
    if src.startswith(("http://", "https://")):
        from ..tools import _http_get
        raw = _http_get(src, timeout=20)
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        return _store(title or (html.unescape(m.group(1)).strip() if m else src), src, "web", [_strip_html(raw)], tags)
    p = _path(src)
    if not p.exists():
        return f"Bulunamadı: {p}"
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.suffix.lower() in (".pdf", ".docx", ".txt", ".md", ".html", ".htm", ".epub", ".pptx")][:300]
        res = [library_add(str(f), "", tags) for f in files]
        ok = [r for r in res if isinstance(r, dict)]
        return {"eklenen": len(ok), "atlanan": len(res) - len(ok), "parça": sum(r["parça"] for r in ok)}
    try:
        pages = _pages_from(p)
    except ImportError as e:
        return f"Bu tür için paket gerekli: {e.name}"
    except Exception as e:
        return f"Okunamadı ({p.name}): {e}"
    return _store(title or p.stem.replace("_", " "), str(p), p.suffix.lower().lstrip("."), pages, tags)


def _store(title, source, kind, pages, tags):
    ch = _chunks(pages)
    if not ch:
        return f"Metin çıkarılamadı (taranmış PDF ise önce OCR gerekir): {title}"
    with _idx_lock:
        old = memory._q("SELECT id FROM lib_docs WHERE source=?", (source,), one=True)
        if old:
            memory._q("DELETE FROM lib_chunks WHERE doc=?", (old["id"],), commit=True)
            memory._q("DELETE FROM lib_docs WHERE id=?", (old["id"],), commit=True)
        did = memory._q("INSERT INTO lib_docs(title,source,kind,pages,chars,added,tags) VALUES(?,?,?,?,?,?,?)",
                        (title, source, kind, len(pages), sum(len(x) for x in pages), time.time(), tags), commit=True)
        for n, (pg, off, t) in enumerate(ch):
            memory._q("INSERT INTO lib_chunks(doc,n,page,off,text) VALUES(?,?,?,?,?)", (did, n, pg, off, t), commit=True)
    _BM.clear()
    return {"belge": did, "başlık": title, "sayfa": len(pages), "parça": len(ch)}


def library_list():
    rows = memory._q("SELECT d.*, (SELECT COUNT(*) FROM lib_chunks c WHERE c.doc=d.id) n FROM lib_docs d ORDER BY added DESC")
    return [{"no": r["id"], "başlık": r["title"], "tür": r["kind"], "sayfa": r["pages"], "parça": r["n"], "etiket": r["tags"] or ""} for r in rows] or "Kütüphane boş."


def library_remove(doc):
    r = _doc(doc)
    if not r:
        return "Belge bulunamadı."
    memory._q("DELETE FROM lib_chunks WHERE doc=?", (r["id"],), commit=True)
    memory._q("DELETE FROM lib_docs WHERE id=?", (r["id"],), commit=True)
    _BM.clear()
    return f"Kaldırıldı: {r['title']}"


def _doc(doc):
    if str(doc).isdigit():
        return memory._q("SELECT * FROM lib_docs WHERE id=?", (int(doc),), one=True)
    return memory._q("SELECT * FROM lib_docs WHERE title LIKE ? ORDER BY added DESC", (f"%{doc}%",), one=True)


_BM = {}


def _bm25_index():
    if _BM:
        return _BM
    rows = memory._q("SELECT c.id, c.doc, c.page, c.text, d.title FROM lib_chunks c JOIN lib_docs d ON d.id=c.doc")
    docs = [(r, Counter(_tok(r["text"]))) for r in rows]
    df = Counter()
    for _, tf in docs:
        df.update(tf.keys())
    avg = sum(sum(tf.values()) for _, tf in docs) / max(1, len(docs))
    _BM.update({"docs": docs, "df": df, "N": len(docs), "avg": avg})
    return _BM


def _bm25(query, k=8, doc_filter=None):
    ix = _bm25_index()
    q = _tok(query)
    if not ix["N"] or not q:
        return []
    k1, b = 1.5, 0.75
    out = []
    for r, tf in ix["docs"]:
        if doc_filter and r["doc"] != doc_filter:
            continue
        L = sum(tf.values())
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (ix["N"] - ix["df"][w] + 0.5) / (ix["df"][w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * L / ix["avg"]))
        if s > 0:
            out.append((s, r))
    out.sort(key=lambda x: -x[0])
    return out[:k]


def library_search(query, limit=6, doc=""):
    d = _doc(doc) if doc else None
    hits = _bm25(query, int(limit or 6) * 2, d["id"] if d else None)
    # vektör ile yeniden sırala (embedding sağlayıcı varsa)
    try:
        from . import semantic
        if hits and semantic._provider()[0]:
            _, vecs = semantic.embed([query] + [h[1]["text"][:1500] for h in hits])
            qv = vecs[0]
            mx = max(h[0] for h in hits)
            hits = sorted(((0.5 * h[0] / mx + 0.5 * semantic._cos(qv, v), h[1]) for h, v in zip(hits, vecs[1:])), key=lambda x: -x[0])
    except Exception:
        pass
    return [{"belge": h[1]["title"], "sayfa": h[1]["page"], "parça": h[1]["id"], "puan": round(h[0], 3), "metin": h[1]["text"][:700]} for h in hits[:int(limit or 6)]] or "Eşleşme yok."


def library_ask(question, doc=""):
    hits = library_search(question, 6, doc)
    if isinstance(hits, str):
        return "Kütüphanede bu soruyla ilgili bir şey bulamadım." + ("" if memory._q("SELECT id FROM lib_docs LIMIT 1", one=True) else " (Kütüphane boş: önce library_add ile belge ekle.)")
    from .. import brain
    ctx = "\n\n".join(f"[{i + 1}] «{h['belge']}» s.{h['sayfa']}:\n{h['metin']}" for i, h in enumerate(hits))
    ans = brain.ask(f"KAYNAKLAR:\n{ctx}\n\nSORU: {question}\n\nYalnızca kaynaklara dayanarak Türkçe cevap ver; her bilgiden sonra [1], [2] gibi kaynak numarası yaz. "
                    "Kaynaklarda yoksa 'kaynaklarda yok' de.", "Sen kaynak gösteren titiz bir araştırma asistanısın.")
    return {"cevap": ans, "kaynaklar": [{"no": i + 1, "belge": h["belge"], "sayfa": h["sayfa"]} for i, h in enumerate(hits)]}


def library_summary(doc, length="orta"):
    d = _doc(doc)
    if not d:
        return "Belge bulunamadı."
    rows = memory._q("SELECT text, page FROM lib_chunks WHERE doc=? ORDER BY n", (d["id"],))
    text = "\n".join(r["text"] for r in rows)
    from .. import brain
    # uzun belgede bölüm bölüm özetle, sonra birleştir
    parts = [text[i:i + 12000] for i in range(0, min(len(text), 120000), 12000)]
    if len(parts) > 1:
        partial = [brain.ask(f"Bu bölümü 5 madde ile özetle:\n{p}", "Kısa ve doğru özetle.") for p in parts]
        text = "\n".join(partial)
    words = {"kısa": "1 paragraf", "orta": "3-5 paragraf ve ana maddeler", "uzun": "ayrıntılı, başlıklı"}.get(length, "3-5 paragraf")
    return {"belge": d["title"], "özet": brain.ask(f"Şu belgeyi {words} olarak Türkçe özetle:\n{text[:24000]}", "Doğru ve yapılandırılmış özet yaz.")}


# ---------------- bilgi grafiği ----------------

def _cooc_graph(texts, top=40):
    """Model olmadan: TF-IDF ile anahtar kavramlar + aynı paragrafta geçme sayısı → kenarlar."""
    paras = [p for t in texts for p in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-ZÇĞİÖŞÜ])", t) if len(p) > 30]
    df, tf = Counter(), Counter()
    surface = {}
    for p in paras:
        words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü][\wçğıöşü]{3,}", p)
        stems = set()
        for w in words:
            st = _tok(w)
            if not st:
                continue
            surface.setdefault(st[0], Counter())[w] += 1
            tf[st[0]] += 1
            stems.add(st[0])
        df.update(stems)
    n = max(1, len(paras))
    score = {w: tf[w] * math.log(1 + n / df[w]) for w in tf if df[w] >= 2 or len(paras) < 4}
    keys = [w for w, _ in sorted(score.items(), key=lambda x: -x[1])[:top]]
    ks = set(keys)
    co = Counter()
    for p in paras:
        st = sorted({_tok(w)[0] for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü][\wçğıöşü]{3,}", p) if _tok(w)} & ks)
        for i in range(len(st)):
            for j in range(i + 1, len(st)):
                co[(st[i], st[j])] += 1
    name = {k: surface[k].most_common(1)[0][0] for k in keys}
    nodes = [{"id": name[k], "w": round(score[k], 2)} for k in keys]
    edges = [{"a": name[a], "b": name[b], "w": c, "rel": ""} for (a, b), c in co.most_common(top * 2) if c >= 1]
    return nodes, edges


def knowledge_graph(topic="", doc="", use_ai=True):
    """3D ilişki grafiği: bir belgeden, kütüphane aramasından ya da JARVIS'in hafızasındaki bilgilerden kavramlar ve ilişkiler."""
    texts, title = [], topic or "Bilgi grafiği"
    if doc:
        d = _doc(doc)
        if not d:
            return "Belge bulunamadı."
        texts = [r["text"] for r in memory._q("SELECT text FROM lib_chunks WHERE doc=? ORDER BY n LIMIT 80", (d["id"],))]
        title = d["title"]
    elif topic:
        h = library_search(topic, 12)
        texts = [x["metin"] for x in h] if isinstance(h, list) else []
    if not texts:
        facts = memory.facts(200)
        texts = [f["fact"] for f in facts]
        title = topic or "JARVIS hafızası"
    nodes, edges = [], []
    if str(use_ai).lower() not in ("false", "0") and texts:
        try:
            from .. import brain
            raw = brain.ask("Aşağıdaki metinden en önemli 15-35 kavramı (kişi, yer, kavram, olay, nesne) ve aralarındaki ilişkileri çıkar. "
                            'SADECE JSON: {"nodes":[{"id":"Ad","type":"kişi|yer|kavram|olay|nesne","info":"kısa açıklama"}],"edges":[{"a":"Ad","b":"Ad","rel":"ilişki fiili"}]}\n\n'
                            + "\n".join(texts)[:14000], "Bilgi grafiği çıkaran bir analistsin. Sadece geçerli JSON yaz.")
            m = re.search(r"\{.*\}", raw, re.S)
            j = json.loads(m.group(0)) if m else {}
            ids = {n["id"] for n in j.get("nodes", []) if n.get("id")}
            nodes = [n for n in j.get("nodes", []) if n.get("id")][:60]
            edges = [e for e in j.get("edges", []) if e.get("a") in ids and e.get("b") in ids][:150]
        except Exception:
            nodes, edges = [], []
    if len(nodes) < 3:
        nodes, edges = _cooc_graph(texts)
        method = "anahtar kavram + birlikte geçme (yerel)"
    else:
        method = "yapay zekâ ile varlık/ilişki çıkarımı"
    if not nodes:
        return "Grafik çıkarılacak yeterli metin yok."
    return {"ui": "graph", "title": title, "nodes": nodes, "edges": edges, "yöntem": method, "düğüm": len(nodes), "bağ": len(edges)}


# ---------------- sesli kitap ----------------

_jobs = {}


def _doc_text(doc_id):
    """Belgenin tam metni; parçalar arasındaki örtüşmeler kayıtlı konumlara göre kesin olarak atılır."""
    out, page, last_end = [], None, 0
    for r in memory._q("SELECT page, off, text FROM lib_chunks WHERE doc=? ORDER BY n", (doc_id,)):
        t, off = r["text"], r["off"]
        if r["page"] != page:
            page, last_end = r["page"], 0
        if off is not None and off < last_end:
            t = t[last_end - off:]
        if off is not None:
            last_end = max(last_end, off + len(r["text"]))
        if t.strip():
            out.append(t)
    return "\n".join(out)


def audiobook(doc, voice="", rate="+0%", max_chars=400000):
    """Belgeyi bölüm bölüm mp3'e dönüştürür (Müzik/JARVIS Sesli Kitaplar). Arka planda çalışır, bitince bildirim gelir."""
    d = _doc(doc)
    if d:
        text = _doc_text(d["id"])
        title = d["title"]
    else:
        p = _path(doc)
        if not p.exists():
            return "Belge bulunamadı (kütüphanedeki adı/numarası ya da dosya yolu ver)."
        text, title = "\n".join(_pages_from(p)), p.stem
    text = text[:int(max_chars)]
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return "Sesli kitap için edge-tts gerekli (pip install edge-tts)."
    from .. import voice as vmod
    lang = vmod.detect_lang(text[:2000])
    v = voice or ("tr-TR-AhmetNeural" if lang == "tr" else "en-GB-RyanNeural")
    out = HOME / "Music" / "JARVIS Sesli Kitaplar" / re.sub(r"[^\w\- ]+", "", title)[:60].strip()
    out.mkdir(parents=True, exist_ok=True)
    parts, cur = [], ""
    for para in re.split(r"\n+", text):
        if len(cur) + len(para) > 9000 and cur:
            parts.append(cur)
            cur = ""
        cur += para + "\n"
    if cur.strip():
        parts.append(cur)
    jid = f"kitap{int(time.time())}"
    _jobs[jid] = {"başlık": title, "bölüm": len(parts), "biten": 0, "klasör": str(out), "durum": "çalışıyor"}

    def run():
        import edge_tts
        for i, t in enumerate(parts, 1):
            f = out / f"{i:03d}.mp3"
            try:
                asyncio.run(edge_tts.Communicate(t, v, rate=rate).save(str(f)))
                _jobs[jid]["biten"] = i
            except Exception as e:
                _jobs[jid]["durum"] = f"hata: {e}"
                memory.notify(f"Sesli kitap durdu ({title}, bölüm {i}): {e}", "error")
                return
        _jobs[jid]["durum"] = "bitti"
        memory.notify(f"Sesli kitap hazır: {title} — {len(parts)} bölüm, {out}", "info")
    threading.Thread(target=run, daemon=True).start()
    dk = round(len(text) / 900, 0)  # ~900 karakter/dk konuşma
    return {"iş": jid, "başlık": title, "bölüm": len(parts), "tahmini_dinleme_dk": dk, "klasör": str(out), "ses": v, "not": "Arka planda üretiliyor; bitince haber vereceğim."}


def audiobook_status():
    return list(_jobs.values()) or "Sesli kitap işi yok."


# ---------------- quiz, kartlar, öğrenme planı ----------------

def quiz_make(topic, count=5, doc="", level="orta"):
    """Konu ya da kütüphanedeki belgeden çoktan seçmeli sorular üretir, ekranda quiz açar ve kartları aralıklı tekrar için kaydeder."""
    from .. import brain
    src = ""
    if doc:
        d = _doc(doc)
        if d:
            src = "\n".join(r["text"] for r in memory._q("SELECT text FROM lib_chunks WHERE doc=? ORDER BY RANDOM() LIMIT 12", (d["id"],)))
            topic = topic or d["title"]
    elif topic:
        h = library_search(topic, 6)
        if isinstance(h, list):
            src = "\n".join(x["metin"] for x in h)
    n = max(1, min(int(count or 5), 20))
    raw = brain.ask(f"'{topic}' konusunda {level} zorlukta {n} adet çoktan seçmeli soru yaz (4 şık). " + (f"SADECE şu kaynaktan sor:\n{src[:10000]}\n" if src else "") +
                    'SADECE JSON dizi: [{"q":"soru","options":["A","B","C","D"],"answer":0,"explain":"neden"}] (answer = doğru şıkkın 0-3 sırası)',
                    "Sen doğru ve öğretici sorular hazırlayan bir öğretmensin. Sadece geçerli JSON yaz.")
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        qs = json.loads(m.group(0)) if m else []
    except Exception:
        qs = []
    qs = [q for q in qs if isinstance(q, dict) and q.get("q") and isinstance(q.get("options"), list) and len(q["options"]) >= 2
          and isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(q["options"])][:n]
    if not qs:
        return "Soru üretilemedi (model geçerli JSON vermedi). Tekrar dene."
    now = time.time()
    for q in qs:
        q["id"] = memory._q("INSERT INTO cards(topic,q,options,answer,explain,due,created) VALUES(?,?,?,?,?,?,?)",
                            (topic, q["q"], json.dumps(q["options"], ensure_ascii=False), q["answer"], q.get("explain", ""), now, now), commit=True)
    return {"ui": "quiz", "title": topic, "questions": qs, "kaynak": "kütüphane" if src else "genel bilgi"}


LEITNER = {1: 0, 2: 1, 3: 3, 4: 7, 5: 16}  # kutu → kaç gün sonra tekrar


def card_answer(card_id, chosen):
    r = memory._q("SELECT * FROM cards WHERE id=?", (int(card_id),), one=True)
    if not r:
        return {"error": "kart yok"}
    ok = int(chosen) == r["answer"]
    box = min(5, r["box"] + 1) if ok else 1
    due = time.time() + LEITNER[box] * 86400 + (600 if not ok else 0)
    memory._q("UPDATE cards SET box=?, due=?, seen=seen+1, correct=correct+? WHERE id=?", (box, due, int(ok), r["id"]), commit=True)
    return {"doğru": ok, "doğru_şık": r["answer"], "açıklama": r["explain"], "kutu": box, "sonraki_tekrar_gün": LEITNER[box]}


def study_review(limit=10, topic=""):
    """Tekrar zamanı gelmiş kartlarla (aralıklı tekrar) quiz açar."""
    q = "SELECT * FROM cards WHERE due<=?" + (" AND topic LIKE ?" if topic else "") + " ORDER BY box, due LIMIT ?"
    args = (time.time(), f"%{topic}%", int(limit or 10)) if topic else (time.time(), int(limit or 10))
    rows = memory._q(q, args)
    if not rows:
        nxt = memory._q("SELECT MIN(due) d FROM cards", one=True)
        return "Şu an tekrar edilecek kart yok." + (f" Sıradaki: {time.strftime('%d.%m %H:%M', time.localtime(nxt['d']))}" if nxt and nxt["d"] else "")
    qs = [{"id": r["id"], "q": r["q"], "options": json.loads(r["options"]), "answer": r["answer"], "explain": r["explain"]} for r in rows]
    return {"ui": "quiz", "title": "Tekrar zamanı" + (f": {topic}" if topic else ""), "questions": qs, "kaynak": "aralıklı tekrar"}


def study_stats():
    rows = memory._q("SELECT topic, COUNT(*) n, SUM(seen) s, SUM(correct) c, AVG(box) b, SUM(CASE WHEN due<=? THEN 1 ELSE 0 END) d FROM cards GROUP BY topic", (time.time(),))
    return [{"konu": r["topic"], "kart": r["n"], "çözülen": r["s"] or 0, "başarı_%": round(100 * (r["c"] or 0) / r["s"]) if r["s"] else 0,
             "ustalık_kutusu": round(r["b"], 1), "tekrar_bekleyen": r["d"]} for r in rows] or "Henüz kart yok."


def learning_plan(goal, weeks=4, hours_per_week=5, add_todos=True):
    """Hedefe göre haftalık öğrenme planı; istenirse her hafta yapılacaklar listesine eklenir."""
    from .. import brain
    w = max(1, min(int(weeks or 4), 52))
    raw = brain.ask(f"Hedef: {goal}. Süre: {w} hafta, haftada {hours_per_week} saat. Gerçekçi, ölçülebilir bir öğrenme planı yap. "
                    'SADECE JSON: {"weeks":[{"week":1,"focus":"konu","tasks":["görev"],"resources":["kaynak adı"],"check":"hafta sonu kendini nasıl test edersin"}]}',
                    "Sen deneyimli bir eğitim koçusun. Sadece geçerli JSON yaz.")
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        plan = json.loads(m.group(0))["weeks"] if m else []
    except Exception:
        plan = []
    if not plan:
        return "Plan oluşturulamadı, tekrar dene."
    pid = memory._q("INSERT INTO learn_plans(goal,plan,created) VALUES(?,?,?)", (goal, json.dumps(plan, ensure_ascii=False), time.time()), commit=True)
    added = 0
    if str(add_todos).lower() not in ("false", "0"):
        try:
            for wk in plan:
                due = time.time() + (int(wk.get("week", 1)) * 7 - 1) * 86400
                for t in wk.get("tasks", [])[:6]:
                    memory._q("INSERT INTO todos(text,due,priority,created) VALUES(?,?,?,?)", (f"[{goal[:30]} · H{wk.get('week')}] {t}", due, "orta", time.time()), commit=True)
                    added += 1
        except Exception:
            pass
    return {"plan_no": pid, "hedef": goal, "hafta": len(plan), "plan": plan, "yapılacaklara_eklenen": added}


TOOLS = {
    "library_add": (library_add, _schema("Bilgi kütüphanesine belge ekler: PDF, Word, TXT, MD, HTML, EPUB, PPTX, bütün bir klasör ya da web sayfası linki.",
                                         {"path": S("dosya/klasör/link"), "title": S("başlık"), "tags": S("etiketler")}, ["path"]), False),
    "library_list": (library_list, _schema("Kütüphanedeki belgeleri listeler.", {}), False),
    "library_remove": (library_remove, _schema("Belgeyi kütüphaneden kaldırır (dosyaya dokunmaz).", {"doc": S("no ya da başlık")}, ["doc"]), True),
    "library_search": (library_search, _schema("Kütüphanede anlamına göre arar (BM25 + vektör), sayfa numarasıyla.", {"query": S("ne"), "limit": {"type": "integer"}, "doc": S("sadece bu belgede")}, ["query"]), False),
    "library_ask": (library_ask, _schema("Kütüphanedeki belgelere dayanarak, kaynak göstererek soruyu cevaplar.", {"question": S("soru"), "doc": S("belirli belge (ops.)")}, ["question"]), False),
    "library_summary": (library_summary, _schema("Kütüphanedeki bir belgeyi özetler (uzun kitapları bölüm bölüm).", {"doc": S("no/başlık"), "length": S("kısa/orta/uzun")}, ["doc"]), False),
    "knowledge_graph": (knowledge_graph, _schema("3D bilgi/ilişki grafiği çizer: bir belgeden, konudan ya da JARVIS hafızasından kavramlar ve bağlantılar.",
                                                 {"topic": S("konu"), "doc": S("belge"), "use_ai": {"type": "boolean"}}), False),
    "audiobook": (audiobook, _schema("Belgeyi/kitabı sesli kitaba (mp3 bölümleri) çevirir, arka planda.", {"doc": S("kütüphane no/başlık ya da dosya"), "voice": S("edge-tts ses adı (ops.)"), "rate": S("+10% gibi")}, ["doc"]), False),
    "audiobook_status": (audiobook_status, _schema("Sesli kitap işlerinin durumu.", {}), False),
    "quiz_make": (quiz_make, _schema("Konu ya da belgeden quiz (çoktan seçmeli) hazırlar ve ekranda açar; kartlar aralıklı tekrar için saklanır.",
                                     {"topic": S("konu"), "count": {"type": "integer"}, "doc": S("belge"), "level": S("kolay/orta/zor")}, ["topic"]), False),
    "study_review": (study_review, _schema("Tekrar zamanı gelen kartlarla quiz açar (aralıklı tekrar).", {"limit": {"type": "integer"}, "topic": S("konu")}), False),
    "study_stats": (study_stats, _schema("Öğrenme istatistikleri: konu başına başarı ve ustalık.", {}), False),
    "learning_plan": (learning_plan, _schema("Haftalık öğrenme planı hazırlar ve görevleri yapılacaklara ekler.",
                                             {"goal": S("hedef"), "weeks": {"type": "integer"}, "hours_per_week": {"type": "number"}, "add_todos": {"type": "boolean"}}, ["goal"]), False),
}
