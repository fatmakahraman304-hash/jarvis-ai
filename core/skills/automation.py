"""Otonom görev sistemi: zamanlanmış/tekrarlayan görevler (sen yokken de çalışır), yapılacaklar listesi,
günlük brifing, kendi kendini test etme, hafıza yedeği geri yükleme."""
import datetime as dt
import json
import subprocess
import sys
import threading
import time
import traceback

from .. import memory
from ..config import ROOT, load_settings, save_settings
from ..tools import N, S, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, prompt TEXT, kind TEXT, at TEXT, weekday INTEGER,
    monthday INTEGER, every_minutes REAL, next_run REAL, enabled INTEGER DEFAULT 1, persona TEXT,
    last_run REAL, last_result TEXT, fails INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS todos(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, due REAL, priority TEXT, done INTEGER DEFAULT 0,
    notified INTEGER DEFAULT 0, created REAL);
""")

GUNLER = {"pazartesi": 0, "salı": 1, "sali": 1, "çarşamba": 2, "carsamba": 2, "perşembe": 3, "persembe": 3,
          "cuma": 4, "cumartesi": 5, "pazar": 6, "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
          "friday": 4, "saturday": 5, "sunday": 6}
_running = set()


def _next_run(t, after=None):
    now = dt.datetime.fromtimestamp(after or time.time())
    if t["kind"] == "interval":
        return now.timestamp() + float(t["every_minutes"]) * 60
    hh, mm = (int(x) for x in (t["at"] or "09:00").split(":")[:2])
    cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if t["kind"] == "once":
        if t.get("next_run"):
            return None
        return (cand if cand > now else cand + dt.timedelta(days=1)).timestamp()
    if t["kind"] == "daily":
        return (cand if cand > now else cand + dt.timedelta(days=1)).timestamp()
    if t["kind"] == "weekdays":
        while cand <= now or cand.weekday() > 4:
            cand += dt.timedelta(days=1)
        return cand.timestamp()
    if t["kind"] == "weekly":
        wd = int(t["weekday"] or 0)
        while cand <= now or cand.weekday() != wd:
            cand += dt.timedelta(days=1)
        return cand.timestamp()
    if t["kind"] == "monthly":
        md = int(t["monthday"] or 1)
        y, m = now.year, now.month
        for _ in range(14):
            try:
                c = dt.datetime(y, m, md, hh, mm)
                if c > now:
                    return c.timestamp()
            except ValueError:
                pass
            m += 1
            if m > 12:
                y, m = y + 1, 1
    return None


def schedule_task(prompt, kind="daily", at="09:00", weekday="", monthday=1, every_minutes=60, date=""):
    """kind: once | daily | weekdays | weekly | monthly | interval."""
    kind = kind.lower()
    wd = GUNLER.get(str(weekday).lower().strip(), weekday if str(weekday).isdigit() else 0)
    t = {"kind": kind, "at": at, "weekday": int(wd or 0), "monthday": int(monthday or 1),
         "every_minutes": float(every_minutes or 60), "next_run": None}
    if kind == "once" and date:
        d = dt.datetime.strptime(f"{date} {at}", "%Y-%m-%d %H:%M")
        nr = d.timestamp()
    else:
        nr = _next_run(t)
    if not nr:
        return "Zaman anlaşılamadı."
    tid = memory._q("INSERT INTO tasks(prompt,kind,at,weekday,monthday,every_minutes,next_run,persona,created) VALUES(?,?,?,?,?,?,?,?,?)",
                    (prompt, kind, at, t["weekday"], t["monthday"], t["every_minutes"], nr,
                     load_settings().get("persona", "jarvis"), time.time()), commit=True)
    return f"Görev #{tid} kuruldu, ilk çalışma: {dt.datetime.fromtimestamp(nr):%d.%m.%Y %H:%M}. Görev: {prompt}"


def list_tasks():
    rows = memory._q("SELECT id, prompt, kind, at, every_minutes, next_run, enabled, last_run, last_result FROM tasks ORDER BY next_run")
    for r in rows:
        r["sonraki"] = dt.datetime.fromtimestamp(r.pop("next_run")).strftime("%d.%m %H:%M") if r.get("next_run") else "-"
        r["son"] = dt.datetime.fromtimestamp(r.pop("last_run")).strftime("%d.%m %H:%M") if r.get("last_run") else "hiç"
        r["last_result"] = (r["last_result"] or "")[:200]
    return rows or "Zamanlanmış görev yok."


def task_control(task_id, action="delete"):
    """action: delete | pause | resume | run_now"""
    tid = int(task_id)
    if action == "delete":
        memory._q("DELETE FROM tasks WHERE id=?", (tid,), commit=True)
        return f"Görev #{tid} silindi."
    if action in ("pause", "resume"):
        memory._q("UPDATE tasks SET enabled=? WHERE id=?", (0 if action == "pause" else 1, tid), commit=True)
        return f"Görev #{tid} {'durduruldu' if action == 'pause' else 'devam ediyor'}."
    if action == "run_now":
        memory._q("UPDATE tasks SET next_run=? WHERE id=?", (time.time(), tid), commit=True)
        return f"Görev #{tid} birazdan çalışacak."
    return "Geçersiz eylem."


def _run_task(t, notify):
    from .. import brain
    _running.add(t["id"])
    try:
        text, confirms, meta = brain.collect(brain.chat(
            f"[OTOMATİK GÖREV #{t['id']} — kullanıcı şu an başında olmayabilir. Görevi eksiksiz yap, sonunda kısa rapor ver.]\n{t['prompt']}",
            t["persona"] or "jarvis", session="auto", source="auto"))
        for c in confirms:
            notify(f"Görev #{t['id']} onay bekliyor: {c['text']} (Onay kodu {c['id']})", "confirm")
        ok = not text.startswith(("Tüm modeller başarısız", "Henüz hiçbir"))
        nr = _next_run(t)
        memory._q("UPDATE tasks SET last_run=?, last_result=?, fails=?, next_run=?, enabled=? WHERE id=?",
                  (time.time(), text[:2000], 0 if ok else (t["fails"] or 0) + 1,
                   nr if ok or (t["fails"] or 0) >= 2 else time.time() + 300,
                   0 if (ok and nr is None) else 1, t["id"]), commit=True)
        notify(f"Görev #{t['id']} {'tamamlandı' if ok else 'başarısız, 5 dk sonra tekrar denenecek'}: {text[:300]}",
               "task" if ok else "error")
    except Exception as e:
        memory._q("UPDATE tasks SET fails=fails+1, next_run=?, last_result=? WHERE id=?",
                  (time.time() + 300, f"Hata: {e}", t["id"]), commit=True)
        traceback.print_exc()
    finally:
        _running.discard(t["id"])


def tick(notify):
    now = time.time()
    try:
        from .control import ESTOP, STATE
        if ESTOP.is_set() or STATE.get("safe_mode"):
            return
    except Exception:
        pass
    for t in memory._q("SELECT * FROM tasks WHERE enabled=1 AND next_run<=?", (now,)):
        if t["id"] in _running:
            continue
        if (t["fails"] or 0) > 3:
            memory._q("UPDATE tasks SET enabled=0 WHERE id=?", (t["id"],), commit=True)
            notify(f"Görev #{t['id']} 3 kez başarısız oldu ve durduruldu.", "error")
            continue
        memory._q("UPDATE tasks SET next_run=? WHERE id=?", (now + 3600, t["id"]), commit=True)  # çift çalışmayı önle
        threading.Thread(target=_run_task, args=(t, notify), daemon=True).start()
    # yapılacaklar: zamanı gelenleri bildir
    for td in memory._q("SELECT id, text FROM todos WHERE done=0 AND notified=0 AND due IS NOT NULL AND due<=?", (now,)):
        memory._q("UPDATE todos SET notified=1 WHERE id=?", (td["id"],), commit=True)
        notify(f"Son tarihi geldi: {td['text']}", "reminder")


# ===================== yapılacaklar =====================
def _due(s):
    if not s:
        return None
    s = s.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            d = dt.datetime.strptime(s, fmt)
            if "%H" not in fmt:
                d = d.replace(hour=9)
            return d.timestamp()
        except ValueError:
            pass
    return None


def todo_add(text, due="", priority="normal"):
    tid = memory._q("INSERT INTO todos(text,due,priority,created) VALUES(?,?,?,?)", (text, _due(due), priority, time.time()), commit=True)
    return f"Yapılacaklara eklendi (#{tid})" + (f", son tarih {due}" if due else "")


def todo_list(include_done=False):
    rows = memory._q("SELECT id, text, due, priority, done FROM todos " + ("" if include_done else "WHERE done=0 ") +
                     "ORDER BY done, CASE priority WHEN 'yüksek' THEN 0 WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, COALESCE(due, 9e12)")
    now = time.time()
    for r in rows:
        if r["due"]:
            r["gecikti"] = r["due"] < now and not r["done"]
            r["due"] = dt.datetime.fromtimestamp(r["due"]).strftime("%d.%m %H:%M")
    return rows or "Yapılacak iş yok."


def todo_update(todo_id, action="done", text="", due=""):
    tid = int(todo_id)
    if action == "done":
        memory._q("UPDATE todos SET done=1 WHERE id=?", (tid,), commit=True)
        return f"#{tid} tamamlandı."
    if action == "delete":
        memory._q("DELETE FROM todos WHERE id=?", (tid,), commit=True)
        return f"#{tid} silindi."
    if action == "edit":
        if text:
            memory._q("UPDATE todos SET text=? WHERE id=?", (text, tid), commit=True)
        if due:
            memory._q("UPDATE todos SET due=?, notified=0 WHERE id=?", (_due(due), tid), commit=True)
        return f"#{tid} güncellendi."
    return "Geçersiz eylem."


# ===================== brifing / bakım =====================
def daily_briefing():
    from ..tools import TOOLS, get_time, list_reminders
    s = load_settings()
    out = {"zaman": get_time()}
    city = s.get("city") or "Istanbul"
    for key, name, args in (("hava", "weather", {"city": city}),
                            ("bugünkü_takvim", "calendar_events", {"days": 1}),
                            ("e_posta", "gmail_stats", {}),
                            ("önemli_okunmamış", "gmail_search", {"query": "is:unread is:important in:inbox newer_than:2d", "max_results": 5}),
                            ("piyasa", "market_price", {"symbols": "dolar,euro,altın,bist100"})):
        if name in TOOLS:
            try:
                out[key] = TOOLS[name][0](**args)
            except Exception as e:
                out[key] = f"alınamadı: {str(e)[:80]}"
    out["yapılacaklar"] = todo_list()
    out["hatırlatıcılar"] = list_reminders()
    out["zamanlanmış_görevler"] = len(memory._q("SELECT id FROM tasks WHERE enabled=1"))
    return out


def morning_briefing(persona=""):
    """Sabah brifingi metni: hava, takvim, önemli e-postalar, piyasa, yapılacaklar, hatırlatıcılar ve günün manşetleri;
    seçili kişiliğin üslubuyla kısa, konuşur gibi."""
    from .. import brain
    data = daily_briefing()
    try:
        from .daily import news
        n = news("", "TR", 5)
        data["manşetler"] = [x.get("başlık") for x in n][:5] if isinstance(n, list) else []
    except Exception:
        pass
    p = persona or load_settings().get("persona", "jarvis")
    txt = brain.ask("Aşağıdaki verilerle kullanıcıya SABAH BRİFİNGİ ver. Selamla, sonra kısa paragraflarla: hava, bugünkü takvim, önemli e-postalar, "
                    "piyasa (dolar/euro/altın), yapılacaklar ve hatırlatıcılar, 3 manşet. 'alınamadı' olan bölümleri atla. En fazla 12 cümle, sesli okunacak; "
                    "madde işareti ve emoji kullanma.\n\n" + json.dumps(data, ensure_ascii=False, default=str)[:9000],
                    "Kullanıcının kişisel asistanısın; kendi karakterinle konuş.", p)
    return txt.strip()


def briefing_tick(notify):
    """Zamanlayıcı: ayarlanan saatte günde bir kez brifingi gönderir (ekran + ses + Telegram)."""
    s = load_settings()
    b = s.get("briefing") or {}
    if not b.get("on"):
        return
    now = time.localtime()
    today = time.strftime("%Y-%m-%d", now)
    if s.get("briefing_last") == today:
        return
    try:
        hh, mm = [int(x) for x in str(b.get("time", "08:00")).split(":")[:2]]
    except ValueError:
        hh, mm = 8, 0
    if (now.tm_hour, now.tm_min) < (hh, mm) or now.tm_hour > hh + 3:  # saati gelmediyse ya da 3 saatten fazla geçtiyse (bilgisayar kapalıydı) bekle
        if now.tm_hour > hh + 3:
            save_settings({"briefing_last": today})
        return
    save_settings({"briefing_last": today})
    try:
        notify(morning_briefing(), "briefing")
    except Exception as e:
        notify(f"Sabah brifingi hazırlanamadı: {e}", "error")


def self_test():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_smoke.py")], capture_output=True, text=True,
                       timeout=180, encoding="utf-8", errors="ignore")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip().startswith(("✓", "✗", "SONUÇ"))]
    return "\n".join(lines) or (r.stdout + r.stderr)[-1500:]


def system_health():
    from .. import llm
    from . import LOAD_ERRORS
    from ..tools import TOOLS
    acts = memory.recent_actions(100)
    fails = [a for a in acts if not a["ok"]]
    return {"araç_sayısı": len(TOOLS), "yüklenemeyen_modüller": list(LOAD_ERRORS) or "yok",
            "bağlı_modeller": [p["id"] for p in llm.status() if p["configured"]],
            "son_100_işlem_başarı_%": round(100 * (len(acts) - len(fails)) / len(acts)) if acts else None,
            "son_hatalar": [f"{a['tool']}: {a['result'][:120]}" for a in fails[:8]]}


_tls = threading.local()


def parallel_agents(tasks, persona=""):
    """Birden fazla alt görevi aynı anda, ayrı 'uzman ajanlarla' yürütür ve sonuçları toplar."""
    from concurrent.futures import ThreadPoolExecutor
    from .. import brain
    if getattr(_tls, "inside", False):
        return "Ajanlar başka ajan başlatamaz."
    try:
        items = json.loads(tasks) if isinstance(tasks, str) and tasks.strip().startswith("[") else tasks
    except Exception:
        items = tasks
    if isinstance(items, str):
        items = [x.strip("-• ").strip() for x in items.splitlines() if x.strip()]
    items = [i if isinstance(i, str) else json.dumps(i, ensure_ascii=False) for i in items][:6]
    if not items:
        return "Görev listesi boş."
    pers = persona or load_settings().get("persona", "jarvis")

    def run(i_task):
        i, task = i_task
        _tls.inside = True
        text, confirms, meta = brain.collect(brain.chat(
            f"[UZMAN AJAN #{i + 1}] Sadece şu alt görevi yap ve sonucu net bir raporla ver (sohbet etme): {task}",
            pers, session=f"agent_{int(time.time())}_{i}", source="auto", hidden=True))
        extra = [c["text"] for c in confirms]
        return {"görev": task, "sonuç": text[:3000], "model": meta.get("model"), "onay_bekleyen": extra}

    with ThreadPoolExecutor(max_workers=min(4, len(items))) as ex:
        results = list(ex.map(run, enumerate(items)))
    return results


def memory_backups(action="list", path=""):
    if action == "restore" and path:
        safety = memory.restore(path)
        return f"Hafıza geri yüklendi. Önceki hâlin yedeği: {safety}"
    if action == "backup":
        return f"Yedeklendi: {memory.backup()}"
    return memory.list_backups() or "Yedek yok."


TOOLS = {
    "morning_briefing": (morning_briefing, _schema("Sabah brifingi: hava, takvim, önemli mailler, piyasa, yapılacaklar ve manşetleri kısa ve konuşur gibi özetler.", {}), False),
    "schedule_task": (schedule_task, _schema(
        "Otomatik görev zamanlar; zamanı gelince JARVIS görevi kendisi yapar ve rapor verir (bilgisayar başında olmasan da). "
        "Örn: her akşam 22:00 'Belgeler klasörünü yedekle', her sabah 08:30 'günlük brifing hazırla', her 30 dk 'önemli e-postaları kontrol et'.",
        {"prompt": S("yapılacak iş, açık talimat"), "kind": {"type": "string", "enum": ["once", "daily", "weekdays", "weekly", "monthly", "interval"]},
         "at": S("SS:DD"), "weekday": S("haftalık için gün adı"), "monthday": N("aylık için ayın günü"),
         "every_minutes": N("interval için dakika"), "date": S("once için YYYY-AA-GG")}, ["prompt"]), False),
    "list_tasks": (list_tasks, _schema("Zamanlanmış görevleri ve son sonuçlarını listeler."), False),
    "task_control": (task_control, _schema("Görevi sil / durdur / devam ettir / hemen çalıştır.",
                                           {"task_id": N("görev no"), "action": {"type": "string", "enum": ["delete", "pause", "resume", "run_now"]}},
                                           ["task_id"]), False),
    "todo_add": (todo_add, _schema("Yapılacaklar listesine iş ekler (son tarihli olabilir).",
                                   {"text": S("iş"), "due": S("YYYY-AA-GG SS:DD"), "priority": {"type": "string", "enum": ["yüksek", "normal", "düşük"]}}, ["text"]), False),
    "todo_list": (todo_list, _schema("Yapılacaklar listesi (gecikenler işaretli).", {"include_done": {"type": "boolean"}}), False),
    "todo_update": (todo_update, _schema("Yapılacak işi tamamla / sil / düzenle.",
                                         {"todo_id": N("no"), "action": {"type": "string", "enum": ["done", "delete", "edit"]}, "text": S("yeni metin"), "due": S("yeni tarih")},
                                         ["todo_id"]), False),
    "daily_briefing": (daily_briefing, _schema("Günlük brifing verisi: saat, hava, takvim, e-posta, piyasa, yapılacaklar, hatırlatıcılar. Bunu sesli ve kısa özetle."), False),
    "self_test": (self_test, _schema("JARVIS kendi otomatik testlerini çalıştırır."), False),
    "system_health": (system_health, _schema("JARVIS'in kendi sağlık raporu: araçlar, modeller, başarısız işlemler."), False),
    "parallel_agents": (parallel_agents, _schema(
        "Büyük bir işi parçalara bölüp alt görevleri AYNI ANDA ayrı uzman ajanlara yaptırır (örn. 3 ürünü ayrı ayrı araştır, "
        "5 dosyayı ayrı ayrı özetle). Sonuçları birleştirip kullanıcıya sen anlat.",
        {"tasks": S("alt görevler: JSON liste veya her satıra bir görev"), "persona": S("kişilik")}, ["tasks"]), False),
    "memory_backups": (memory_backups, _schema("Hafıza yedeklerini listeler, yedek alır veya geri yükler.",
                                               {"action": {"type": "string", "enum": ["list", "backup", "restore"]}, "path": S("geri yüklenecek yedek")}),
                       lambda a: a.get("action") == "restore"),
}
