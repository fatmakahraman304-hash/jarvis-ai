"""Ekranı görme, fare/klavye kontrolü, pencere yönetimi, kamera.

Fare ve klavye işlemleri varsayılan olarak onay ister. Ayarlar > Genel > "Ekran kontrolünde onay isteme"
açılırsa JARVIS bilgisayarı kendi başına kullanabilir.
"""
import io
import json
import re
import sys
import time

from .. import llm
from ..config import DATA, load_settings
from ..tools import N, S, _schema

IS_WIN = sys.platform.startswith("win")
_last_shot = {"scale": 1.0, "ox": 0, "oy": 0, "w": 0, "h": 0}

if IS_WIN:
    import ctypes
    from ctypes import wintypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    U32 = ctypes.windll.user32


def _need_win():
    if not IS_WIN:
        raise RuntimeError("Bu özellik Windows'ta çalışır.")


# ===================== ekran =====================
def _grab(max_w=1600):
    try:
        from PIL import ImageGrab
    except ImportError:
        raise RuntimeError("Ekranı görmek için 'pillow' gerekli (requirements-extra.txt).")
    img = ImageGrab.grab(all_screens=True)
    ox = oy = 0
    if IS_WIN:
        ox, oy = U32.GetSystemMetrics(76), U32.GetSystemMetrics(77)  # sanal ekran başlangıcı
    scale = 1.0
    if img.width > max_w:
        scale = img.width / max_w
        img = img.resize((max_w, int(img.height / scale)))
    _last_shot.update(scale=scale, ox=ox, oy=oy, w=img.width, h=img.height)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=80)
    return buf.getvalue()


def screen_look(question="Ekranda ne var? Açık pencereleri, önemli yazıları ve hata mesajlarını anlat."):
    img = _grab()
    return llm.vision(question + "\nKısa ve net Türkçe cevap ver.", img, "image/jpeg")


def screen_find(target):
    img = _grab()
    prompt = (f"Bu ekran görüntüsü {_last_shot['w']}x{_last_shot['h']} piksel. '{target}' öğesinin (buton, yazı, ikon) "
              "merkezinin piksel koordinatını bul. SADECE şu JSON'u yaz: {\"x\": sayı, \"y\": sayı, \"bulundu\": true/false, \"not\": \"kısa\"}")
    ans = llm.vision(prompt, img, "image/jpeg")
    m = re.search(r"\{.*\}", ans, re.S)
    if not m:
        return f"Konum çıkarılamadı: {ans[:200]}"
    try:
        d = json.loads(m.group(0))
    except Exception:
        return f"Konum çıkarılamadı: {ans[:200]}"
    if not d.get("bulundu", True):
        return f"'{target}' ekranda bulunamadı. {d.get('not', '')}"
    sx = int(float(d["x"]) * _last_shot["scale"] + _last_shot["ox"])
    sy = int(float(d["y"]) * _last_shot["scale"] + _last_shot["oy"])
    return {"x": sx, "y": sy, "not": d.get("not", ""), "ipucu": "mouse_click ile bu koordinata tıklayabilirsin"}


def read_screen_text():
    img = _grab(2000)
    return llm.vision("Ekrandaki tüm okunabilir yazıyı olduğu gibi, düzenini koruyarak yaz (OCR).", img, "image/jpeg")


# ===================== fare / klavye =====================
def mouse_click(x, y, button="left", double=False):
    _need_win()
    U32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    down, up = (0x0008, 0x0010) if button == "right" else (0x0002, 0x0004)
    for _ in range(2 if double else 1):
        U32.mouse_event(down, 0, 0, 0, 0)
        U32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.08)
    return f"{'Çift ' if double else ''}tıklandı ({x},{y})."


def mouse_move(x, y):
    _need_win()
    U32.SetCursorPos(int(x), int(y))
    return f"Fare ({x},{y}) konumunda."


def mouse_scroll(amount=-5):
    _need_win()
    U32.mouse_event(0x0800, 0, 0, int(amount) * 120, 0)
    return "Kaydırıldı."


VK = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "windows": 0x5B,
      "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
      "delete": 0x2E, "del": 0x2E, "space": 0x20, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
      "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "printscreen": 0x2C, "insert": 0x2D,
      **{f"f{i}": 0x6F + i for i in range(1, 13)}}


def _vk(k):
    k = k.strip().lower()
    if k in VK:
        return VK[k]
    if len(k) == 1 and k.isalnum():
        return ord(k.upper())
    raise ValueError(f"Bilinmeyen tuş: {k}")


def key_press(keys):
    """'ctrl+c', 'alt+tab', 'enter', 'win+d' gibi."""
    _need_win()
    codes = [_vk(k) for k in keys.replace(" ", "").split("+")]
    for c in codes:
        U32.keybd_event(c, 0, 0, 0)
        time.sleep(0.02)
    for c in reversed(codes):
        U32.keybd_event(c, 0, 2, 0)
    return f"Basıldı: {keys}"


def _set_clipboard(text):
    _need_win()
    CF_UNICODETEXT = 13
    k32 = ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    U32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = text.encode("utf-16-le") + b"\x00\x00"
    for _ in range(5):
        if U32.OpenClipboard(0):
            break
        time.sleep(0.05)
    try:
        U32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0042, len(data))
        p = k32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k32.GlobalUnlock(h)
        U32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        U32.CloseClipboard()


def _get_clipboard():
    _need_win()
    CF_UNICODETEXT = 13
    k32 = ctypes.windll.kernel32
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    U32.GetClipboardData.restype = ctypes.c_void_p
    if not U32.OpenClipboard(0):
        return ""
    try:
        h = U32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k32.GlobalLock(h)
        text = ctypes.wstring_at(p)
        k32.GlobalUnlock(h)
        return text
    finally:
        U32.CloseClipboard()


def type_text(text, press_enter=False):
    """Türkçe karakterler dahil her metni yazar (pano + Ctrl+V)."""
    _need_win()
    old = ""
    try:
        old = _get_clipboard()
    except Exception:
        pass
    try:
        from . import habits
        habits._state["clip"] = text
    except Exception:
        pass
    _set_clipboard(text)
    time.sleep(0.05)
    key_press("ctrl+v")
    time.sleep(0.15)
    if press_enter:
        key_press("enter")
    try:
        if old:
            time.sleep(0.2)
            from . import habits
            habits._state["clip"] = old
            _set_clipboard(old)
    except Exception:
        pass
    return f"Yazıldı ({len(text)} karakter){' ve Enter' if press_enter else ''}."


def clipboard(action="get", text=""):
    if action == "set":
        _set_clipboard(text)
        return "Panoya kopyalandı."
    return _get_clipboard()[:5000] or "(pano boş)"


# ===================== pencereler =====================
def _windows():
    _need_win()
    out = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if U32.IsWindowVisible(hwnd):
            n = U32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                U32.GetWindowTextW(hwnd, buf, n + 1)
                out.append((hwnd, buf.value))
        return True
    U32.EnumWindows(EnumProc(cb), 0)
    return [w for w in out if w[1] != "Program Manager"]


def list_windows():
    return [t for _, t in _windows()][:40]


def window_control(title, action="focus"):
    """action: focus | minimize | maximize | restore | close"""
    wins = [w for w in _windows() if title.lower() in w[1].lower()]
    if not wins:
        return f"'{title}' başlıklı pencere yok."
    hwnd, name = wins[0]
    if action == "close":
        U32.PostMessageW(hwnd, 0x0010, 0, 0)
    elif action == "minimize":
        U32.ShowWindow(hwnd, 6)
    elif action == "maximize":
        U32.ShowWindow(hwnd, 3)
    elif action == "restore":
        U32.ShowWindow(hwnd, 9)
    else:
        U32.ShowWindow(hwnd, 9)
        U32.keybd_event(0x12, 0, 0, 0)  # Windows'un odak kısıtını aşmak için Alt
        U32.SetForegroundWindow(hwnd)
        U32.keybd_event(0x12, 0, 2, 0)
    return f"'{name}': {action}"


# ===================== kamera =====================
def camera_look(question="Kamerada ne görüyorsun?"):
    try:
        import cv2  # type: ignore
    except ImportError:
        return ("Sunucu tarafı kamera için 'opencv-python' gerekli. Alternatif: arayüzdeki 📷 KAMERA düğmesi "
                "tarayıcı kamerasıyla aynı işi yapar.")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if IS_WIN else 0)
    time.sleep(0.6)
    ok, frame = False, None
    for _ in range(6):
        ok, frame = cap.read()
    cap.release()
    if not ok:
        return "Kameradan görüntü alınamadı."
    ok, jpg = cv2.imencode(".jpg", frame)
    path = DATA / "screens" / f"kamera_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(jpg.tobytes())
    return llm.vision(question + "\nKısa ve net Türkçe cevap ver.", jpg.tobytes(), "image/jpeg")


def image_analyze(path, question="Bu görselde ne var? Yazı varsa oku."):
    from ..tools import _path
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
    data = p.read_bytes()
    if len(data) > 4_000_000:
        try:
            from PIL import Image
            im = Image.open(p)
            im.thumbnail((1800, 1800))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=85)
            data, m = buf.getvalue(), "image/jpeg"
        except Exception:
            return "Görsel çok büyük."
    else:
        m = mime.get(p.suffix.lower().lstrip("."), "image/png")
    return llm.vision(question, data, m)


def _control_crit(_a):
    return not load_settings().get("auto_control", False)


TOOLS = {
    "screen_look": (screen_look, _schema("Ekranı GÖRÜR ve soruyu cevaplar (ne açık, hata ne diyor, ne yapmalıyım).",
                                         {"question": S("ekran hakkında soru")}), False),
    "screen_find": (screen_find, _schema("Ekranda bir buton/yazı/ikonun koordinatını bulur.",
                                         {"target": S("bulunacak öğe, örn 'Gönder butonu'")}, ["target"]), False),
    "read_screen_text": (read_screen_text, _schema("Ekrandaki tüm yazıyı okur (OCR)."), False),
    "mouse_click": (mouse_click, _schema("Ekranda koordinata tıklar.", {"x": N("x"), "y": N("y"),
                    "button": {"type": "string", "enum": ["left", "right"]}, "double": {"type": "boolean"}}, ["x", "y"]), _control_crit),
    "mouse_move": (mouse_move, _schema("Fareyi taşır.", {"x": N("x"), "y": N("y")}, ["x", "y"]), False),
    "mouse_scroll": (mouse_scroll, _schema("Sayfayı kaydırır (eksi aşağı).", {"amount": N("adım")}), False),
    "key_press": (key_press, _schema("Tuş/kısayol basar: 'enter', 'ctrl+s', 'alt+tab', 'win+d', 'ctrl+shift+esc'.",
                                     {"keys": S("tuşlar")}, ["keys"]), _control_crit),
    "type_text": (type_text, _schema("Aktif pencereye metin yazar (Türkçe dahil).",
                                     {"text": S("metin"), "press_enter": {"type": "boolean"}}, ["text"]), _control_crit),
    "clipboard": (clipboard, _schema("Panoyu okur ('get') veya panoya yazar ('set').",
                                     {"action": {"type": "string", "enum": ["get", "set"]}, "text": S("metin")}), False),
    "list_windows": (list_windows, _schema("Açık pencereleri listeler."), False),
    "window_control": (window_control, _schema("Pencereyi öne getirir / küçültür / büyütür / kapatır.",
                                               {"title": S("pencere başlığının bir parçası"),
                                                "action": {"type": "string", "enum": ["focus", "minimize", "maximize", "restore", "close"]}},
                                               ["title"]), lambda a: a.get("action") == "close"),
    "camera_look": (camera_look, _schema("Web kamerasından bakar ve soruyu cevaplar (nesne, yazı, belge, QR).",
                                         {"question": S("soru")}), False),
    "image_analyze": (image_analyze, _schema("Bir görsel dosyasını analiz eder / içindeki yazıyı okur.",
                                             {"path": S("dosya yolu"), "question": S("soru")}, ["path"]), False),
}
