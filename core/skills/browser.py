"""Tarayıcı otomasyonu (Playwright): bilgisayarındaki Edge/Chrome'u JARVIS'e ait ayrı bir profille açar; sayfaya gider, okur,
tıklanabilir öğeleri numaralandırır, tıklar, form doldurur, tuşa basar, sekmeleri yönetir, sayfayı görerek soruları cevaplar.

Güvenlik: şifre alanlarına yazmaz (şifreler için kasadaki vault_type kullanılır); 'satın al, öde, sipariş, gönder, sil, onayla'
gibi düğmeler ve form gönderme her zaman onay ister. JARVIS profili kendi çerezlerini tutar (data/browser_profile)."""
import os
import queue
import re
import threading

from ..config import DATA, load_settings
from ..tools import S, _schema

RISKY = re.compile(r"satın|öde|ödeme|sipariş|gönder|sil|onayla|kaydol|abone|bağış|havale|transfer|buy|pay|checkout|order|purchase|submit|send|delete|confirm|subscribe", re.I)
_jobs = queue.Queue()
_thread = None
_state = {"ctx": None, "page": None, "pw": None}


def _worker():
    while True:
        fn, args, box = _jobs.get()
        try:
            box["v"] = fn(*args)
        except Exception as e:
            box["e"] = e
        box["ev"].set()


def _call(fn, *args, timeout=90):
    """Playwright nesneleri tek bir iş parçacığına bağlıdır: tüm çağrılar aynı işçide çalışır."""
    global _thread
    if not _thread or not _thread.is_alive():
        _thread = threading.Thread(target=_worker, daemon=True, name="browser")
        _thread.start()
    box = {"ev": threading.Event()}
    _jobs.put((fn, args, box))
    if not box["ev"].wait(timeout):
        raise TimeoutError("Tarayıcı yanıt vermedi.")
    if "e" in box:
        raise box["e"]
    return box["v"]


def _ctx():
    st = _state
    if st["ctx"]:
        try:
            st["ctx"].pages  # kapanmış mı
            if st["ctx"].pages or st["page"]:
                return st["ctx"]
        except Exception:
            st["ctx"] = None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Tarayıcı otomasyonu için: pip install playwright (Edge/Chrome zaten yüklü olduğu için ayrıca tarayıcı indirmeye gerek yok).")
    if not st["pw"]:
        st["pw"] = sync_playwright().start()
    prof = DATA / "browser_profile"
    prof.mkdir(parents=True, exist_ok=True)
    headless = os.environ.get("JARVIS_BROWSER_HEADLESS") == "1"
    last = None
    for ch in ([os.environ.get("JARVIS_BROWSER_CHANNEL")] if os.environ.get("JARVIS_BROWSER_CHANNEL") else []) + ["msedge", "chrome", None]:
        try:
            kw = {"headless": headless, "viewport": None if not headless else {"width": 1280, "height": 860}, "locale": "tr-TR"}
            if ch:
                kw["channel"] = ch
            st["ctx"] = st["pw"].chromium.launch_persistent_context(str(prof), **kw)
            st["ctx"].on("page", lambda p: _state.__setitem__("page", p))
            st["page"] = st["ctx"].pages[0] if st["ctx"].pages else st["ctx"].new_page()
            return st["ctx"]
        except Exception as e:
            last = e
    raise RuntimeError(f"Tarayıcı açılamadı: {last}")


def _page():
    ctx = _ctx()
    p = _state["page"]
    if not p or p.is_closed():
        p = ctx.pages[-1] if ctx.pages else ctx.new_page()
        _state["page"] = p
    return p


_INDEX_JS = r"""() => {
  const out = []; let i = 0;
  document.querySelectorAll('[data-jv]').forEach(e => e.removeAttribute('data-jv'));
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],[contenteditable=true],summary';
  for (const e of document.querySelectorAll(sel)) {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (r.width < 2 || r.height < 2 || cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (r.bottom < 0 || r.top > innerHeight * 3) continue;
    i++; e.setAttribute('data-jv', i);
    const tag = e.tagName.toLowerCase(), type = (e.getAttribute('type') || '').toLowerCase();
    let label = e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('placeholder') || e.getAttribute('title') || e.getAttribute('name') || e.getAttribute('alt') || '';
    if (e.id) { const l = document.querySelector(`label[for="${CSS.escape(e.id)}"]`); if (l) label = l.innerText + (label ? ' · ' + label : ''); }
    const kind = tag === 'a' ? 'bağlantı' : tag === 'button' || e.getAttribute('role') === 'button' ? 'düğme' : tag === 'select' ? 'seçim' : tag === 'textarea' ? 'metin alanı' :
                 tag === 'input' ? (type === 'checkbox' ? 'onay kutusu' : type === 'radio' ? 'seçenek' : type === 'submit' ? 'gönder düğmesi' : type === 'password' ? 'ŞİFRE alanı' : 'giriş alanı') : (e.getAttribute('role') || tag);
    out.push(`[${i}] ${kind}: ${label.replace(/\s+/g, ' ').trim().slice(0, 80)}`);
    if (i >= 150) break;
  }
  return out;
}"""


def _read(max_chars=6000):
    p = _page()
    try:
        p.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
    els = p.evaluate(_INDEX_JS)
    text = p.evaluate("() => document.body ? document.body.innerText : ''") or ""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {"başlık": p.title(), "adres": p.url, "metin": text[:int(max_chars)] + ("…" if len(text) > int(max_chars) else ""), "öğeler": els,
            "not": "Tıklamak/doldurmak için öğe numarasını kullan (ör. browser_click('12'))."}


def _loc(p, target):
    t = str(target).strip().lstrip("#[").rstrip("]")
    if t.isdigit():
        loc = p.locator(f'[data-jv="{t}"]')
        if loc.count():
            return loc.first
        raise RuntimeError(f"#{t} numaralı öğe yok; önce browser_read çağır (numaralar sayfa değişince yenilenir).")
    for fn in (lambda: p.get_by_role("button", name=t), lambda: p.get_by_role("link", name=t), lambda: p.get_by_label(t), lambda: p.get_by_placeholder(t),
               lambda: p.get_by_text(t, exact=False)):
        try:
            loc = fn()
            if loc.count():
                return loc.first
        except Exception:
            continue
    raise RuntimeError(f"'{target}' sayfada bulunamadı.")


def _label_of(p, target):
    try:
        loc = _loc(p, target)
        return loc.evaluate("e => (e.innerText || e.value || e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('type') || '')") or ""
    except Exception:
        return str(target)


# ---------------- araçlar ----------------

def browser_open(url, new_tab=False):
    def run():
        ctx = _ctx()
        u = url if re.match(r"^[a-z]+:", url) else ("https://" + url if "." in url and " " not in url else "https://www.google.com/search?q=" + url)
        p = ctx.new_page() if str(new_tab).lower() in ("true", "1") else _page()
        _state["page"] = p
        p.goto(u, wait_until="domcontentloaded", timeout=30000)
        return _read(3000)
    return _call(run)


def browser_read(max_chars=6000):
    return _call(_read, max_chars)


def browser_click(target):
    def run():
        p = _page()
        loc = _loc(p, target)
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=8000)
        try:
            p.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        return {"tıklandı": str(target), **_read(2500)}
    return _call(run)


def browser_fill(field, value, submit=False):
    def run():
        p = _page()
        loc = _loc(p, field)
        typ = (loc.get_attribute("type") or "").lower()
        if typ == "password" or "password" in (loc.get_attribute("autocomplete") or ""):
            return "Şifre alanına yapay zekâ üzerinden yazmam. Alana tıkla, sonra 'kasadan … şifresini yaz' de (vault_type şifreyi modele göstermeden yazar)."
        tag = loc.evaluate("e => e.tagName.toLowerCase()")
        if tag == "select":
            try:
                loc.select_option(label=str(value))
            except Exception:
                loc.select_option(str(value))
        elif typ in ("checkbox", "radio"):
            (loc.check if str(value).lower() not in ("false", "0", "hayır", "kaldır") else loc.uncheck)()
        else:
            loc.fill(str(value), timeout=8000)
        if str(submit).lower() in ("true", "1"):
            loc.press("Enter")
            try:
                p.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
        return {"dolduruldu": str(field), "değer": str(value)[:60], "gönderildi": str(submit).lower() in ("true", "1")}
    return _call(run)


def browser_press(key):
    def run():
        k = {"enter": "Enter", "tab": "Tab", "esc": "Escape", "geri": "Alt+ArrowLeft", "aşağı": "PageDown", "yukarı": "PageUp"}.get(str(key).lower(), key)
        _page().keyboard.press(k)
        return f"Basıldı: {k}"
    return _call(run)


def browser_tabs(action="list", index=0):
    def run():
        ctx = _ctx()
        pages = [p for p in ctx.pages if not p.is_closed()]
        a = str(action).lower()
        if a in ("switch", "geç") and 0 < int(index) <= len(pages):
            _state["page"] = pages[int(index) - 1]
            _state["page"].bring_to_front()
        elif a in ("close", "kapat") and 0 < int(index) <= len(pages):
            pages[int(index) - 1].close()
        elif a in ("new", "yeni"):
            _state["page"] = ctx.new_page()
        elif a in ("back", "geri"):
            _page().go_back()
        pages = [p for p in ctx.pages if not p.is_closed()]
        cur = _state["page"]
        return [{"no": i + 1, "başlık": (p.title() or "")[:70], "adres": p.url, "etkin": p == cur} for i, p in enumerate(pages)]
    return _call(run)


def browser_look(question="Bu sayfada ne var?"):
    def run():
        return _page().screenshot(type="jpeg", quality=80)
    img = _call(run)
    from .. import llm
    return llm.vision(question, img, "image/jpeg")


def browser_close():
    def run():
        try:
            if _state["ctx"]:
                _state["ctx"].close()
        finally:
            _state["ctx"] = _state["page"] = None
        return "Tarayıcı kapatıldı."
    return _call(run)


def _click_crit(a):
    if RISKY.search(str(a.get("target", ""))):
        return True
    if str(a.get("target", "")).strip().lstrip("#[").rstrip("]").isdigit() and _state["page"]:
        try:
            if RISKY.search(_call(_label_of, _page(), a.get("target"), timeout=10)):
                return True
        except Exception:
            pass
    return not load_settings().get("auto_control", False)


def _fill_crit(a):
    return str(a.get("submit", "")).lower() in ("true", "1") or not load_settings().get("auto_control", False)


TOOLS = {
    "browser_open": (browser_open, _schema("Tarayıcıda (JARVIS'in Edge/Chrome profili) adres ya da arama açar ve sayfayı okur; tıklanabilir öğeleri numaralı listeler.",
                                           {"url": S("adres ya da aranacak şey"), "new_tab": {"type": "boolean"}}, ["url"]), False),
    "browser_read": (browser_read, _schema("Açık sayfanın metnini ve numaralı tıklanabilir öğelerini okur.", {"max_chars": {"type": "integer"}}), False),
    "browser_click": (browser_click, _schema("Sayfada bir öğeye tıklar (öğe numarası ya da görünen yazısı).", {"target": S("öğe no ya da yazı")}, ["target"]), _click_crit),
    "browser_fill": (browser_fill, _schema("Form alanını doldurur (öğe no, etiket ya da yer tutucu yazısı); seçim kutusu ve onay kutusu da olur. Şifre alanına yazmaz.",
                                           {"field": S("alan"), "value": S("değer"), "submit": {"type": "boolean", "description": "Enter ile gönder"}}, ["field", "value"]), _fill_crit),
    "browser_press": (browser_press, _schema("Tarayıcıda tuşa basar (Enter, Tab, Escape, PageDown…).", {"key": S("tuş")}, ["key"]), False),
    "browser_tabs": (browser_tabs, _schema("Sekmeler: list, switch (index), close (index), new, back.", {"action": S("list/switch/close/new/back"), "index": {"type": "integer"}}), False),
    "browser_look": (browser_look, _schema("Tarayıcı sayfasının görüntüsüne bakıp soruyu cevaplar (grafik, düzen, görsel içerik).", {"question": S("soru")}), False),
    "browser_close": (browser_close, _schema("JARVIS tarayıcısını kapatır.", {}), False),
}
