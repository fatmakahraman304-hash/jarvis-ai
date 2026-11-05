"""Günlük hayat: alarm, notlar, alışveriş listesi, haberler; proje merkezi: kod projesi oluşturma, test çalıştırma, GitHub."""
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

from .. import memory
from ..tools import N, S, _http_get, _path, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, tags TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS shopping(id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, qty TEXT, done INTEGER DEFAULT 0, ts REAL);
CREATE TABLE IF NOT EXISTS alarms(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, label TEXT, repeat TEXT, fired INTEGER DEFAULT 0);
""")


# ===================== ALARM =====================
def set_alarm(time_hhmm, label="Alarm", repeat="once", date=""):
    """repeat: once | daily | weekdays"""
    hh, mm = (int(x) for x in str(time_hhmm).replace(".", ":").split(":")[:2])
    now = dt.datetime.now()
    base = dt.datetime.strptime(date, "%Y-%m-%d") if date else now
    t = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if t <= now:
        t += dt.timedelta(days=1)
    aid = memory._q("INSERT INTO alarms(at,label,repeat) VALUES(?,?,?)", (t.timestamp(), label, repeat), commit=True)
    return f"Alarm #{aid} kuruldu: {t:%d.%m %H:%M} ({label})"


def list_alarms():
    return [{"no": a["id"], "zaman": dt.datetime.fromtimestamp(a["at"]).strftime("%d.%m %H:%M"), "etiket": a["label"], "tekrar": a["repeat"]}
            for a in memory._q("SELECT * FROM alarms WHERE fired=0 ORDER BY at")] or "Kurulu alarm yok."


def delete_alarm(alarm_id):
    memory._q("DELETE FROM alarms WHERE id=?", (int(alarm_id),), commit=True)
    return "Alarm silindi."


def alarm_tick(notify):
    now = time.time()
    for a in memory._q("SELECT * FROM alarms WHERE fired=0 AND at<=?", (now,)):
        notify(f"⏰ ALARM: {a['label']}", "alarm")
        if a["repeat"] in ("daily", "weekdays"):
            t = dt.datetime.fromtimestamp(a["at"]) + dt.timedelta(days=1)
            while a["repeat"] == "weekdays" and t.weekday() > 4:
                t += dt.timedelta(days=1)
            memory._q("UPDATE alarms SET at=? WHERE id=?", (t.timestamp(), a["id"]), commit=True)
        else:
            memory._q("UPDATE alarms SET fired=1 WHERE id=?", (a["id"],), commit=True)


# ===================== NOTLAR =====================
def note_add(body, title="", tags=""):
    nid = memory._q("INSERT INTO notes(title,body,tags,ts) VALUES(?,?,?,?)", (title or body[:40], body, tags, time.time()), commit=True)
    return f"Not #{nid} kaydedildi."


def note_search(query="", limit=15):
    if query:
        rows = memory._q("SELECT * FROM notes WHERE body LIKE ? OR title LIKE ? OR tags LIKE ? ORDER BY id DESC LIMIT ?", (f"%{query}%",) * 3 + (int(limit),))
    else:
        rows = memory._q("SELECT * FROM notes ORDER BY id DESC LIMIT ?", (int(limit),))
    return [{"no": r["id"], "başlık": r["title"], "not": r["body"][:500], "etiket": r["tags"], "tarih": time.strftime("%d.%m.%Y", time.localtime(r["ts"]))} for r in rows] or "Not yok."


def note_delete(note_id):
    memory._q("DELETE FROM notes WHERE id=?", (int(note_id),), commit=True)
    return "Not silindi."


# ===================== ALIŞVERİŞ =====================
def shopping_add(items):
    added = []
    for it in re.split(r"[,\n;]+", str(items)):
        it = it.strip()
        if not it:
            continue
        m = re.match(r"^(\d+[.,]?\d*\s*(?:kg|g|gr|lt|l|adet|paket|kutu|şişe)?)\s+(.+)$", it, re.I)
        qty, name = (m.group(1), m.group(2)) if m else ("", it)
        memory._q("INSERT INTO shopping(item,qty,ts) VALUES(?,?,?)", (name, qty, time.time()), commit=True)
        added.append(f"{qty} {name}".strip())
    return f"Listeye eklendi: {', '.join(added)}"


def shopping_list(include_done=False):
    rows = memory._q("SELECT * FROM shopping " + ("" if include_done else "WHERE done=0 ") + "ORDER BY done, id")
    return [{"no": r["id"], "ürün": f"{r['qty']} {r['item']}".strip(), "alındı": bool(r["done"])} for r in rows] or "Alışveriş listesi boş."


def shopping_update(item, action="done"):
    if action == "clear":
        memory._q("DELETE FROM shopping WHERE done=1", commit=True)
        return "Alınanlar listeden temizlendi."
    rows = memory._q("SELECT id FROM shopping WHERE id=? OR item LIKE ?", (int(item) if str(item).isdigit() else -1, f"%{item}%"))
    for r in rows:
        if action == "delete":
            memory._q("DELETE FROM shopping WHERE id=?", (r["id"],), commit=True)
        else:
            memory._q("UPDATE shopping SET done=1 WHERE id=?", (r["id"],), commit=True)
    return f"{len(rows)} ürün güncellendi."


# ===================== HABERLER =====================
def news(topic="", country="TR", limit=10):
    lang = {"TR": "tr", "US": "en", "GB": "en", "DE": "de", "FR": "fr"}.get(country.upper(), "en")
    if topic:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": topic, "hl": lang, "gl": country.upper(), "ceid": f"{country.upper()}:{lang}"})
    else:
        url = f"https://news.google.com/rss?hl={lang}&gl={country.upper()}&ceid={country.upper()}:{lang}"
    xml = _http_get(url)
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)[: int(limit)]
    out = []
    for it in items:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        s = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it)
        l = re.search(r"<link>(.*?)</link>", it)
        out.append({"başlık": html.unescape(t.group(1)) if t else "", "kaynak": html.unescape(s.group(1)) if s else "",
                    "tarih": d.group(1)[5:22] if d else "", "link": l.group(1) if l else ""})
    return out or "Haber bulunamadı."


# ===================== PROJE MERKEZİ =====================
def _projects_dir():
    d = _path("belgeler") / "JARVIS_Projeler"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_project(name, files, description=""):
    """files: JSON {"dosya/yolu.py": "içerik", ...}. Proje klasörü + README + git deposu oluşturur."""
    try:
        fm = json.loads(files) if isinstance(files, str) else files
    except Exception:
        return "files geçerli JSON olmalı."
    slug = re.sub(r"[^\w\-]+", "_", name.strip())[:60] or "proje"
    root = _projects_dir() / slug
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for rel, content in fm.items():
        p = (root / rel).resolve()
        if root.resolve() not in p.parents and p != root.resolve():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        written.append(rel)
    if not (root / "README.md").exists():
        (root / "README.md").write_text(f"# {name}\n\n{description}\n", encoding="utf-8")
    if shutil.which("git") and not (root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=root)
        subprocess.run(["git", "add", "-A"], cwd=root)
        subprocess.run(["git", "-c", "user.name=JARVIS", "-c", "user.email=jarvis@localhost", "commit", "-qm", "İlk sürüm (JARVIS)"], cwd=root)
    return {"proje": str(root), "dosyalar": written, "git": (root / ".git").exists()}


def run_project(path, command=""):
    """Projede testleri ya da verilen komutu çalıştırır (pytest, npm test, python main.py...)."""
    root = _path(path)
    if not root.exists():
        root = _projects_dir() / path
    if not root.exists():
        return "Proje bulunamadı."
    if not command:
        if (root / "package.json").exists():
            command = "npm test"
        elif any(root.rglob("test_*.py")):
            import importlib.util
            command = f'"{sys.executable}" -m pytest -q' if importlib.util.find_spec("pytest") else f'"{sys.executable}" -m unittest discover -v'

        elif (root / "main.py").exists():
            command = f'"{sys.executable}" main.py'
        else:
            return "Çalıştırılacak test veya main.py yok; command ver."
    r = subprocess.run(command, cwd=root, shell=True, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=300)
    return {"komut": command, "çıkış_kodu": r.returncode, "başarılı": r.returncode == 0, "çıktı": (r.stdout + "\n" + r.stderr)[-4000:]}


def list_projects():
    return [{"ad": p.name, "yol": str(p), "git": (p / ".git").exists(), "değişti": time.strftime("%d.%m %H:%M", time.localtime(p.stat().st_mtime))}
            for p in sorted(_projects_dir().iterdir()) if p.is_dir()] or "Proje yok."


def _gh(*args, cwd=None, timeout=120):
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI (gh) kurulu değil: 'winget install GitHub.cli' sonra 'gh auth login'.")
    r = subprocess.run(["gh", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout)
    return (r.stdout or r.stderr).strip()


def github(action, repo="", path="", message="", title="", body=""):
    """action: repos | issues | create_repo | push | pr | status | clone"""
    if action == "repos":
        return _gh("repo", "list", "--limit", "30")
    if action == "issues":
        return _gh("issue", "list", "-R", repo, "--limit", "20")
    if action == "status":
        return _gh("pr", "status", cwd=str(_path(path)) if path else None)
    if action == "clone":
        return _gh("repo", "clone", repo, str(_projects_dir() / repo.split("/")[-1]))
    if action == "create_repo":
        root = _path(path) if path else None
        return _gh("repo", "create", repo, "--private", *(["--source", str(root), "--push"] if root else []))
    if action == "push":
        root = _path(path)
        subprocess.run(["git", "add", "-A"], cwd=root)
        subprocess.run(["git", "commit", "-qm", message or "JARVIS güncellemesi"], cwd=root)
        r = subprocess.run(["git", "push"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
        return (r.stdout + r.stderr).strip() or "Gönderildi."
    if action == "pr":
        return _gh("pr", "create", "--title", title or message or "JARVIS", "--body", body or "JARVIS tarafından hazırlandı.", cwd=str(_path(path)))
    return "Geçerli: repos, issues, status, clone, create_repo, push, pr"


TOOLS = {
    "set_alarm": (set_alarm, _schema("Alarm kurar (zamanı gelince sesli çalar).", {"time_hhmm": S("SS:DD"), "label": S("etiket"),
                  "repeat": {"type": "string", "enum": ["once", "daily", "weekdays"]}, "date": S("YYYY-AA-GG (isteğe bağlı)")}, ["time_hhmm"]), False),
    "list_alarms": (list_alarms, _schema("Kurulu alarmlar."), False),
    "delete_alarm": (delete_alarm, _schema("Alarm siler.", {"alarm_id": N("no")}, ["alarm_id"]), False),
    "note_add": (note_add, _schema("Not kaydeder.", {"body": S("not"), "title": S("başlık"), "tags": S("etiketler")}, ["body"]), False),
    "note_search": (note_search, _schema("Notlarda arar / listeler.", {"query": S("ara")}), False),
    "note_delete": (note_delete, _schema("Not siler.", {"note_id": N("no")}, ["note_id"]), False),
    "shopping_add": (shopping_add, _schema("Alışveriş listesine ekler (virgülle, miktar olabilir: '2 kg elma, süt').", {"items": S("ürünler")}, ["items"]), False),
    "shopping_list": (shopping_list, _schema("Alışveriş listesi."), False),
    "shopping_update": (shopping_update, _schema("Ürünü alındı işaretle / sil / alınanları temizle.", {"item": S("ürün veya no"),
                        "action": {"type": "string", "enum": ["done", "delete", "clear"]}}, ["item"]), False),
    "news": (news, _schema("Güncel haber başlıkları (Google Haberler).", {"topic": S("konu (boş: manşetler)"), "country": S("TR, US, DE..."), "limit": N("kaç")}), False),
    "create_project": (create_project, _schema("Yazdığın kodla yeni yazılım projesi oluşturur (Belgeler/JARVIS_Projeler) ve git deposu başlatır.",
                       {"name": S("proje adı"), "files": S('JSON {"main.py":"...","test_main.py":"..."}'), "description": S("açıklama")}, ["name", "files"]), False),
    "run_project": (run_project, _schema("Projede testleri veya komutu çalıştırır, sonucu verir.", {"path": S("proje adı/yolu"), "command": S("komut (boş: otomatik)")}, ["path"]), True),
    "list_projects": (list_projects, _schema("JARVIS projeleri."), False),
    "github": (github, _schema("GitHub: repos, issues, status, clone, create_repo, push, pr (gh CLI ile).",
               {"action": S("eylem"), "repo": S("sahip/depo"), "path": S("yerel proje"), "message": S("commit mesajı"), "title": S("PR başlığı"), "body": S("PR açıklaması")}, ["action"]),
               lambda a: a.get("action") in ("create_repo", "push", "pr")),
}
