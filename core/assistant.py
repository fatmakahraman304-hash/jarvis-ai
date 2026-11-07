"""Local project knowledge, durable task evidence and quiet, evidence-based initiative.

No model calls or desktop actions run in the initiative worker. Every suggestion
has a source and a persisted cooldown, including across application restarts.
"""
import json
import functools
import re
import threading
import time
import unicodedata

from . import memory
from .config import load_settings

_activity_lock = threading.Lock()
_active_turns = 0


def track_activity(function):
    @functools.wraps(function)
    def stream(*args, **kwargs):
        global _active_turns
        with _activity_lock:
            _active_turns += 1
        try:
            yield from function(*args, **kwargs)
        finally:
            with _activity_lock:
                _active_turns -= 1
    return stream

memory.ensure("""
CREATE TABLE IF NOT EXISTS project_notes(
 project TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
 updated REAL NOT NULL, PRIMARY KEY(project,key));
CREATE TABLE IF NOT EXISTS assistant_tasks(
 id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL, goal TEXT NOT NULL,
 status TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', created REAL, updated REAL);
CREATE INDEX IF NOT EXISTS assistant_session ON assistant_tasks(session,updated);
CREATE TABLE IF NOT EXISTS task_evidence(
 id INTEGER PRIMARY KEY AUTOINCREMENT, task INTEGER NOT NULL, tool TEXT NOT NULL,
 ok INTEGER NOT NULL, result TEXT NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS initiative_sent(key TEXT PRIMARY KEY, ts REAL NOT NULL);
""")


def _text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'1–{maximum} karakter metin gerekli.')
    return value.strip()


def tokens(value):
    value = unicodedata.normalize('NFKD', value.casefold().replace('ı', 'i'))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return set(re.findall(r'[a-z0-9]{3,}', value))


def project_note(project, action='read', key='', value=''):
    project = _text(project, 120)
    if action == 'set':
        key, value = _text(key, 160), _text(value, 4000)
        memory._q('INSERT INTO project_notes VALUES(?,?,?,?) ON CONFLICT(project,key) '
                  'DO UPDATE SET value=excluded.value,updated=excluded.updated',
                  (project, key, value, time.time()), commit=True)
    elif action == 'delete':
        memory._q('DELETE FROM project_notes WHERE project=? AND key=?',
                  (project, _text(key, 160)), commit=True)
    elif action != 'read':
        raise ValueError('read/set/delete kullan.')
    return memory._q('SELECT project,key,value,updated FROM project_notes WHERE project=? '
                     'ORDER BY updated DESC LIMIT 100', (project,))


def context(query, limit=12):
    """Bounded local retrieval, Turkish insensitive, latest value wins by key."""
    terms = tokens(query)
    notes = memory._q('SELECT project,key,value,updated FROM project_notes ORDER BY updated DESC LIMIT 1000')
    ranked = sorted(notes, key=lambda r: len(terms & tokens(' '.join(
        (r['project'], r['key'], r['value'])))), reverse=True)
    return [r for r in ranked if terms & tokens(' '.join(
        (r['project'], r['key'], r['value'])))][:limit]


def start_task(session, goal):
    now = time.time()
    return memory._q('INSERT INTO assistant_tasks(session,goal,status,created,updated) '
                     "VALUES(?,?,'running',?,?)", (session, goal[:6000], now, now), commit=True)


def checkpoint(task, tool, result, ok):
    # Store output evidence, not raw tool arguments (which may contain secrets).
    memory._q('INSERT INTO task_evidence(task,tool,ok,result,ts) VALUES(?,?,?,?,?)',
              (task, tool, int(ok), str(result)[:1600], time.time()), commit=True)
    memory._q('UPDATE assistant_tasks SET updated=? WHERE id=?', (time.time(), task), commit=True)


def finish_task(task, status, summary):
    if status not in {'finished', 'paused', 'blocked', 'needs_confirmation', 'cancelled'}:
        raise ValueError('Geçersiz görev durumu.')
    memory._q('UPDATE assistant_tasks SET status=?,summary=?,updated=? WHERE id=?',
              (status, summary[:3000], time.time(), task), commit=True)


def task_journal(task_id=0, session='main', include_finished=False):
    if task_id:
        rows = memory._q('SELECT * FROM assistant_tasks WHERE id=? AND session=?', (int(task_id), session))
    else:
        rows = memory._q('SELECT * FROM assistant_tasks WHERE session=? ' +
                         ('' if include_finished else "AND status NOT IN ('finished','cancelled') ") +
                         'ORDER BY updated DESC LIMIT 8', (session,))
    for row in rows:
        evidence = memory._q('SELECT tool,ok,result,ts FROM task_evidence WHERE task=? ORDER BY id DESC LIMIT 8', (row['id'],))
        row['evidence'] = list(reversed(evidence))
        if row['status'] == 'running':
            row['note'] = 'Kayıtlı durum; çalışan arka plan süreci olduğunun kanıtı değildir.'
    return rows


def resume_context(session):
    rows = task_journal(session=session)
    return rows[0] if rows else None


def tick(notify, now=None):
    settings = load_settings()
    now = time.time() if now is None else now
    hour = time.localtime(now).tm_hour
    if _active_turns or not settings.get('initiative_enabled', True) or settings.get('guest_mode') or not 9 <= hour < 22:
        return
    from .skills.control import ESTOP
    if ESTOP.is_set():
        return
    # Never interrupt an active conversation or input task.
    latest = memory._q('SELECT ts FROM messages ORDER BY id DESC LIMIT 1', one=True)
    if latest and now - latest['ts'] < 180:
        return
    last = memory._q('SELECT max(ts) ts FROM initiative_sent', one=True)
    if last and last['ts'] and now - last['ts'] < 3600:
        return
    candidates = []
    pending = memory._q("SELECT id,goal,status,updated FROM assistant_tasks WHERE status IN ('paused','blocked','needs_confirmation','running') AND updated<? ORDER BY updated DESC LIMIT 1", (now-600,))
    if pending:
        task = pending[0]
        candidates.append((f"task:{task['id']}:{int(task['updated'])}",
            f"Yarım kalan bir işimiz var: {task['goal'][:180]}. Kayıtlı son durum: {task['status']}. 'Devam et' dersen güncel durumu kontrol edip sürdürebilirim."))
    from .skills.reasoning import macro_suggestions
    for suggestion in macro_suggestions(3)[:1]:
        signature = json.dumps(suggestion['steps'], sort_keys=True, ensure_ascii=False)
        import hashlib
        key = 'habit:' + hashlib.sha256(signature.encode()).hexdigest()[:20]
        names = ', '.join(step['tool'] for step in suggestion['steps'])
        candidates.append((key, f"Aynı iki adımlı işi {suggestion['count']} kez yaptık ({names}). İstersen buna tek bir sesli komut atayabiliriz."))
    for key, text in candidates:
        sent = memory._q('SELECT ts FROM initiative_sent WHERE key=?', (key,), one=True)
        if sent and now - sent['ts'] < 86400 * 7:
            continue
        notify(text, 'suggestion')
        memory._q('INSERT INTO initiative_sent VALUES(?,?) ON CONFLICT(key) DO UPDATE SET ts=excluded.ts', (key, now), commit=True)
        break
