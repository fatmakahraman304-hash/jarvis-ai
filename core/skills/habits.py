"""Alışkanlıklar ve masaüstü farkındalığı: uygulama kullanım süreleri, pano geçmişi, Windows bildirimleri.
Hepsi sadece bu bilgisayarda saklanır; Ayarlar'dan kapatılabilir."""
import datetime as dt
import sys
import time

from .. import memory
from ..config import load_settings
from ..tools import N, S, _schema

IS_WIN = sys.platform.startswith("win")

memory.ensure("""
CREATE TABLE IF NOT EXISTS app_usage(day TEXT, app TEXT, minutes REAL, PRIMARY KEY(day, app));
CREATE TABLE IF NOT EXISTS clip_history(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, ts REAL);
""")

_state = {"last_usage": 0.0, "last_clip": 0.0, "clip": None, "skip_next_clip": False}


def _foreground_app():
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        import psutil
        name = psutil.Process(pid.value).name().replace(".exe", "")
    except Exception:
        name = "?"
    return name


def tick():
    """Sunucunun zamanlayıcısı her 5 sn çağırır."""
    if not IS_WIN:
        return
    s = load_settings()
    now = time.time()
    if s.get("track_usage", True) and now - _state["last_usage"] >= 60:
        _state["last_usage"] = now
        try:
            # kullanıcı boşta mı? (5 dk hareketsizse sayma)
            import ctypes

            class LII(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LII(ctypes.sizeof(LII), 0)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            idle = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000
            app = _foreground_app()
            if app and idle < 300:
                day = dt.date.today().isoformat()
                memory._q("INSERT INTO app_usage(day,app,minutes) VALUES(?,?,1) ON CONFLICT(day,app) DO UPDATE SET minutes=minutes+1",
                          (day, app), commit=True)
        except Exception:
            pass
    if s.get("clipboard_history", True) and now - _state["last_clip"] >= 3:
        _state["last_clip"] = now
        try:
            from .computer import _get_clipboard
            txt = _get_clipboard()
            if txt and txt != _state["clip"]:
                first = _state["clip"] is None
                _state["clip"] = txt
                if not first and len(txt) < 20000 and txt.strip():
                    memory._q("INSERT INTO clip_history(text, ts) VALUES(?,?)", (txt, now), commit=True)
                    memory._q("DELETE FROM clip_history WHERE id NOT IN (SELECT id FROM clip_history ORDER BY id DESC LIMIT 100)", commit=True)
        except Exception:
            pass


def usage_report(days=1):
    since = (dt.date.today() - dt.timedelta(days=int(days) - 1)).isoformat()
    rows = memory._q("SELECT app, SUM(minutes) m FROM app_usage WHERE day>=? GROUP BY app ORDER BY m DESC LIMIT 15", (since,))
    total = sum(r["m"] for r in rows)
    return {"gün": int(days), "toplam_saat": round(total / 60, 1),
            "uygulamalar": [{"uygulama": r["app"], "dakika": int(r["m"]), "%": round(100 * r["m"] / total) if total else 0} for r in rows]} \
        if rows else "Henüz kullanım verisi yok (Windows'ta arka planda dakikada bir kaydedilir)."


def work_habits(days=14):
    rows = memory._q("SELECT day, app, minutes FROM app_usage WHERE day>=?",
                     ((dt.date.today() - dt.timedelta(days=int(days))).isoformat(),))
    if not rows:
        return "Yeterli veri yok."
    by_day = {}
    for r in rows:
        by_day[r["day"]] = by_day.get(r["day"], 0) + r["minutes"]
    wd = {}
    for d, m in by_day.items():
        k = dt.date.fromisoformat(d).strftime("%A")
        wd.setdefault(k, []).append(m)
    return {"günlük_ortalama_saat": round(sum(by_day.values()) / len(by_day) / 60, 1),
            "en_yoğun_gün": max(by_day, key=by_day.get),
            "haftanın_günlerine_göre_ortalama_saat": {k: round(sum(v) / len(v) / 60, 1) for k, v in wd.items()},
            "en_çok_kullanılan": usage_report(int(days)).get("uygulamalar", [])[:5] if isinstance(usage_report(int(days)), dict) else []}


def clipboard_history(limit=15, query=""):
    if query:
        rows = memory._q("SELECT text, ts FROM clip_history WHERE text LIKE ? ORDER BY id DESC LIMIT ?", (f"%{query}%", int(limit)))
    else:
        rows = memory._q("SELECT text, ts FROM clip_history ORDER BY id DESC LIMIT ?", (int(limit),))
    return [{"zaman": dt.datetime.fromtimestamp(r["ts"]).strftime("%d.%m %H:%M"), "metin": r["text"][:300]} for r in rows] or "Pano geçmişi boş."


def clipboard_restore(index=1):
    rows = memory._q("SELECT text FROM clip_history ORDER BY id DESC LIMIT 1 OFFSET ?", (int(index) - 1,))
    if not rows:
        return "Öyle bir kayıt yok."
    from .computer import _set_clipboard
    _set_clipboard(rows[0]["text"])
    return "Panoya geri koyuldu."


def read_notifications(limit=10, app=""):
    if not IS_WIN:
        return "Bildirim okuma Windows'ta çalışır."
    try:
        import asyncio
        try:  # yeni modüler paketler (hazır kurulumlu, derleyici gerektirmez)
            from winrt.windows.ui.notifications import NotificationKinds  # type: ignore
            from winrt.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus  # type: ignore
        except ImportError:
            from winsdk.windows.ui.notifications import NotificationKinds  # type: ignore
            from winsdk.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus  # type: ignore
    except ImportError:
        return "Bildirimleri okumak için: pip install winrt-Windows.UI.Notifications winrt-Windows.UI.Notifications.Management"

    async def run():
        lst = UserNotificationListener.current
        st = await lst.request_access_async()
        if st != UserNotificationListenerAccessStatus.ALLOWED:
            return "Bildirim erişimi verilmedi: Ayarlar > Gizlilik ve güvenlik > Bildirimler'den Python'a izin ver."
        items = await lst.get_notifications_async(NotificationKinds.TOAST)
        out = []
        for n in list(items)[-int(limit) * 3:]:
            try:
                name = n.app_info.display_info.display_name
            except Exception:
                name = "?"
            if app and app.lower() not in name.lower():
                continue
            texts = []
            try:
                b = n.notification.visual.get_binding("ToastGeneric")
                texts = [t.text for t in b.get_text_elements()]
            except Exception:
                pass
            out.append({"uygulama": name, "zaman": n.creation_time.strftime("%H:%M") if hasattr(n.creation_time, "strftime") else "",
                        "metin": " — ".join(texts)[:300]})
        return out[-int(limit):] or "Bildirim yok."
    return asyncio.run(run())


TOOLS = {
    "usage_report": (usage_report, _schema("Hangi uygulamada ne kadar zaman geçirildiği (ekran süresi).", {"days": N("kaç gün")}), False),
    "work_habits": (work_habits, _schema("Çalışma alışkanlıkları: günlük ortalama, yoğun günler, en çok kullanılanlar.", {"days": N("kaç gün")}), False),
    "clipboard_history": (clipboard_history, _schema("Pano geçmişi (kopyalananlar).", {"limit": N("kaç"), "query": S("ara")}), False),
    "clipboard_restore": (clipboard_restore, _schema("Pano geçmişindeki bir kaydı tekrar panoya koyar.", {"index": N("1=en son")}), False),
    "read_notifications": (read_notifications, _schema("Windows bildirimlerini okur (WhatsApp, Discord, e-posta...).",
                                                       {"limit": N("kaç"), "app": S("sadece bu uygulama")}), False),
}
