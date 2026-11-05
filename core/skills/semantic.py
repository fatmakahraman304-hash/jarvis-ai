"""Anlamsal (vektör) hafıza: kelimesi kelimesine değil, ANLAMINA göre hatırlama.
'geçen ay tatil hakkında ne konuşmuştuk' gibi soruları cevaplar. Ücretsiz Gemini/Mistral/Ollama embedding kullanır;
hiçbiri yoksa normal kelime aramasına düşer."""
import json
import math
import threading
import time
import urllib.request

from .. import llm, memory
from ..config import env
from ..tools import N, S, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS vectors(kind TEXT, ref INTEGER, model TEXT, vec TEXT, PRIMARY KEY(kind, ref, model));
""")

EMBED = [("gemini", "gemini-embedding-001"), ("mistral", "mistral-embed"), ("ollama", "nomic-embed-text"),
         ("custom", "text-embedding-3-small")]
_lock = threading.Lock()
_last = [0.0]
_disabled_until = [0.0]


def _provider():
    for pid, model in EMBED:
        if llm.configured(pid):
            return pid, env(f"{pid.upper()}_EMBED_MODEL") or model
    return None, None


def embed(texts):
    pid, model = _provider()
    if not pid:
        return None, None
    req = urllib.request.Request(llm._base(pid) + "/embeddings", data=json.dumps({"model": model, "input": texts}).encode(),
                                 headers=llm._headers(pid), method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    return f"{pid}:{model}", [d["embedding"] for d in sorted(data["data"], key=lambda d: d.get("index", 0))]


def _cos(a, b):
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb + 1e-9)


def index_tick():
    """Arka planda yeni bilgileri ve konuşmaları vektörleştirir (sunucu zamanlayıcısı çağırır)."""
    now = time.time()
    if now - _last[0] < 30 or now < _disabled_until[0] or not _lock.acquire(blocking=False):
        return
    _last[0] = now
    try:
        pid, model = _provider()
        if not pid:
            return
        tag = f"{pid}:{model}"
        todo = memory._q("SELECT 'fact' kind, id ref, fact txt FROM facts WHERE id NOT IN (SELECT ref FROM vectors WHERE kind='fact' AND model=?) LIMIT 40", (tag,))
        todo += memory._q("SELECT 'msg' kind, id ref, content txt FROM messages WHERE role IN ('user','assistant') AND length(content)>15 "
                          "AND id NOT IN (SELECT ref FROM vectors WHERE kind='msg' AND model=?) ORDER BY id DESC LIMIT 40", (tag,))
        if not todo:
            return
        m, vecs = embed([t["txt"][:2000] for t in todo])
        for t, v in zip(todo, vecs):
            memory._q("INSERT OR REPLACE INTO vectors(kind,ref,model,vec) VALUES(?,?,?,?)",
                      (t["kind"], t["ref"], m, json.dumps([round(x, 5) for x in v])), commit=True)
    except Exception as e:
        print("[anlamsal hafıza]", str(e)[:120])
        _disabled_until[0] = now + 600
    finally:
        _lock.release()


def deep_recall(query, limit=8):
    try:
        m, qv = embed([query])
    except Exception:
        m = None
    if not m:
        from ..tools import recall
        return recall(query)
    rows = memory._q("SELECT kind, ref, vec FROM vectors WHERE model=?", (m,))
    scored = sorted(((_cos(qv[0], json.loads(r["vec"])), r["kind"], r["ref"]) for r in rows), reverse=True)[: int(limit)]
    out = []
    for score, kind, ref in scored:
        if score < 0.45:
            continue
        if kind == "fact":
            f = memory._q("SELECT fact FROM facts WHERE id=?", (ref,), one=True)
            if f:
                out.append({"tür": "bilgi", "benzerlik": round(score, 2), "metin": f["fact"]})
        else:
            msg = memory._q("SELECT role, content, ts FROM messages WHERE id=?", (ref,), one=True)
            if msg:
                out.append({"tür": "konuşma", "benzerlik": round(score, 2), "kim": msg["role"],
                            "tarih": time.strftime("%d.%m.%Y", time.localtime(msg["ts"])), "metin": msg["content"][:400]})
    return out or "Anlamca benzer bir şey bulunamadı."


TOOLS = {
    "deep_recall": (deep_recall, _schema("Hafızada ANLAMINA göre arar (eski konuşmalar, kayıtlı bilgiler). 'Geçen sefer ne konuşmuştuk', 'X hakkında ne biliyorsun' için.",
                                         {"query": S("ne"), "limit": N("kaç sonuç")}, ["query"]), False),
}
