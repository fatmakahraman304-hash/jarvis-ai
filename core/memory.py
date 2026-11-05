"""Kalıcı hafıza (SQLite): sohbet geçmişi, öğrenilen bilgiler, hatırlatıcılar, işlem kaydı."""
import json
import sqlite3
import threading
import time

from .config import DATA

DB_PATH = DATA / "jarvis_memory.db"
_lock = threading.RLock()


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


_db = _conn()
with _lock:
    _db.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session TEXT, role TEXT, content TEXT, persona TEXT, source TEXT,
            provider TEXT, ts REAL);
        CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session, id);
        CREATE TABLE IF NOT EXISTS facts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT, category TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS reminders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT, due REAL, fired INTEGER DEFAULT 0, created REAL);
        CREATE TABLE IF NOT EXISTS actions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool TEXT, args TEXT, result TEXT, ok INTEGER, ts REAL);
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT, kind TEXT, ts REAL);
        """
    )
    _db.commit()


def ensure(sql):
    """Yetenek modülleri kendi tablolarını oluşturmak için kullanır."""
    with _lock:
        _db.executescript(sql)
        _db.commit()


def _q(sql, args=(), one=False, commit=False):
    with _lock:
        cur = _db.execute(sql, args)
        if commit:
            _db.commit()
            return cur.lastrowid
        rows = cur.fetchall()
    rows = [dict(r) for r in rows]
    return (rows[0] if rows else None) if one else rows


# ---- sohbet ----
def add_message(session, role, content, persona="", source="web", provider=""):
    return _q("INSERT INTO messages(session,role,content,persona,source,provider,ts) VALUES(?,?,?,?,?,?,?)",
              (session, role, content, persona, source, provider, time.time()), commit=True)


def history(session, limit=20):
    rows = _q("SELECT role, content, persona, ts FROM messages WHERE session=? ORDER BY id DESC LIMIT ?",
              (session, limit))
    return list(reversed(rows))


def search_messages(query, limit=10):
    return _q("SELECT session, role, content, persona, ts FROM messages WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
              (f"%{query}%", limit))


def clear_session(session):
    _q("DELETE FROM messages WHERE session=?", (session,), commit=True)


# ---- bilgiler ----
def add_fact(fact, category="genel"):
    existing = _q("SELECT id FROM facts WHERE fact=?", (fact,), one=True)
    if existing:
        return existing["id"]
    return _q("INSERT INTO facts(fact,category,ts) VALUES(?,?,?)", (fact, category, time.time()), commit=True)


def facts(limit=200):
    return _q("SELECT id, fact, category, ts FROM facts ORDER BY id DESC LIMIT ?", (limit,))


def find_facts(query, limit=20):
    words = [w for w in query.lower().split() if len(w) > 2] or [query.lower()]
    out, seen = [], set()
    for w in words:
        for r in _q("SELECT id, fact, category FROM facts WHERE lower(fact) LIKE ? LIMIT ?", (f"%{w}%", limit)):
            if r["id"] not in seen:
                seen.add(r["id"])
                out.append(r)
    return out[:limit]


def delete_fact(fid):
    _q("DELETE FROM facts WHERE id=?", (fid,), commit=True)


def forget_matching(text):
    rows = find_facts(text)
    for r in rows:
        delete_fact(r["id"])
    return len(rows)


# ---- hatırlatıcılar / bildirimler ----
def add_reminder(text, due):
    return _q("INSERT INTO reminders(text,due,created) VALUES(?,?,?)", (text, due, time.time()), commit=True)


def due_reminders():
    rows = _q("SELECT id, text, due FROM reminders WHERE fired=0 AND due<=?", (time.time(),))
    for r in rows:
        _q("UPDATE reminders SET fired=1 WHERE id=?", (r["id"],), commit=True)
    return rows


def pending_reminders():
    return _q("SELECT id, text, due FROM reminders WHERE fired=0 ORDER BY due")


def notify(text, kind="info"):
    return _q("INSERT INTO notifications(text,kind,ts) VALUES(?,?,?)", (text, kind, time.time()), commit=True)


def notifications_since(last_id):
    return _q("SELECT id, text, kind, ts FROM notifications WHERE id>? ORDER BY id", (int(last_id),))


def last_notification_id():
    r = _q("SELECT max(id) AS m FROM notifications", one=True)
    return (r or {}).get("m") or 0


# ---- işlem kaydı ----
def log_action(tool, args, result, ok=True):
    _q("INSERT INTO actions(tool,args,result,ok,ts) VALUES(?,?,?,?,?)",
       (tool, json.dumps(args, ensure_ascii=False)[:2000], str(result)[:4000], 1 if ok else 0, time.time()), commit=True)


def recent_actions(limit=50):
    return _q("SELECT tool, args, result, ok, ts FROM actions ORDER BY id DESC LIMIT ?", (limit,))


def backup():
    dst = DATA / f"backup_{time.strftime('%Y%m%d_%H%M%S')}.db"
    with _lock:
        _db.commit()
        dst_conn = sqlite3.connect(dst)
        _db.backup(dst_conn)
        dst_conn.close()
    return str(dst)


def restore(path):
    """Yedekten geri yükler (mevcut hafızanın da yedeği alınır)."""
    import pathlib
    src = pathlib.Path(path)
    if not src.exists():
        raise FileNotFoundError(path)
    safety = backup()
    with _lock:
        src_conn = sqlite3.connect(src)
        src_conn.backup(_db)
        src_conn.close()
    return safety


def list_backups():
    return sorted((str(p) for p in DATA.glob("backup_*.db")), reverse=True)
