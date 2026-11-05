"""Şifre kasası.

- Windows'ta şifreler Windows DPAPI ile şifrelenir: sadece SENİN Windows hesabın çözebilir.
- Diğer sistemlerde 'cryptography' (Fernet) ile şifrelenir.
- Şifreler ASLA yapay zekâ modeline gönderilmez: araçlar sadece isimleri görür; şifre panoya kopyalanır
  veya aktif alana yazılır (her ikisi de onay ister). Kasaya ekleme/görme sadece bilgisayardaki arayüzden yapılır.
"""
import base64
import json
import secrets
import string
import sys
import time

from ..config import DATA
from ..tools import N, S, _schema

VAULT = DATA / "vault.json"
IS_WIN = sys.platform.startswith("win")


# ---------------- şifreleme ----------------
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return _BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    def _protect(data: bytes) -> bytes:
        inp, _keep = _blob(data)
        out = _BLOB()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(inp), "JARVIS", None, None, None, 0, ctypes.byref(out)):
            raise OSError("DPAPI şifreleme başarısız")
        res = ctypes.string_at(out.pbData, out.cbData)
        ctypes.windll.kernel32.LocalFree(out.pbData)
        return res

    def _unprotect(data: bytes) -> bytes:
        inp, _keep = _blob(data)
        out = _BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
            raise OSError("DPAPI çözme başarısız (başka Windows hesabı?)")
        res = ctypes.string_at(out.pbData, out.cbData)
        ctypes.windll.kernel32.LocalFree(out.pbData)
        return res
else:
    def _key():
        kf = DATA / "vault.key"
        if not kf.exists():
            from cryptography.fernet import Fernet
            kf.write_bytes(Fernet.generate_key())
            kf.chmod(0o600)
        return kf.read_bytes()

    def _protect(data: bytes) -> bytes:
        from cryptography.fernet import Fernet
        return Fernet(_key()).encrypt(data)

    def _unprotect(data: bytes) -> bytes:
        from cryptography.fernet import Fernet
        return Fernet(_key()).decrypt(data)


def _load():
    try:
        return json.loads(VAULT.read_text())
    except Exception:
        return {}


def _save(v):
    VAULT.write_text(json.dumps(v, ensure_ascii=False, indent=1))


# ---------------- arayüz (sadece yerel) ----------------
def save_entry(name, username, secret, url="", note=""):
    v = _load()
    v[name] = {"user": username, "url": url, "note": note, "ts": time.time(),
               "secret": base64.b64encode(_protect(secret.encode("utf-8"))).decode()}
    _save(v)


def reveal(name):
    e = _load()[name]
    return _unprotect(base64.b64decode(e["secret"])).decode("utf-8")


def delete_entry(name):
    v = _load()
    v.pop(name, None)
    _save(v)


def entries():
    return [{"ad": k, "kullanıcı": e.get("user", ""), "site": e.get("url", ""), "not": e.get("note", "")} for k, e in sorted(_load().items())]


def _find(name):
    v = _load()
    if name in v:
        return name
    for k, e in v.items():
        if name.lower() in k.lower() or name.lower() in e.get("url", "").lower():
            return k
    raise KeyError(f"Kasada '{name}' yok.")


# ---------------- araçlar (model şifreyi görmez) ----------------
def vault_list():
    return entries() or "Kasa boş. Ayarlar > KASA'dan ekleyebilirsin."


def _secure_copy(val):
    from .computer import _set_clipboard
    try:
        from . import habits
        habits._state["clip"] = val  # pano geçmişine şifre düşmesin
    except Exception:
        pass
    _set_clipboard(val)


def vault_copy(name, field="password"):
    k = _find(name)
    val = reveal(k) if field == "password" else _load()[k].get("user", "")
    _secure_copy(val)
    _clear_later()
    return f"'{k}' {'şifresi' if field == 'password' else 'kullanıcı adı'} panoya kopyalandı (30 sn sonra silinecek)."


def vault_type(name, field="password", press_enter=False):
    from .computer import type_text
    k = _find(name)
    val = reveal(k) if field == "password" else _load()[k].get("user", "")
    type_text(val, press_enter=press_enter)
    return f"'{k}' {'şifresi' if field == 'password' else 'kullanıcı adı'} aktif alana yazıldı."


def vault_generate(name, username="", length=20, url=""):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+?"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(int(length)))
        if any(c.isdigit() for c in pw) and any(c.isupper() for c in pw) and any(c in "!@#$%^&*-_=+?" for c in pw):
            break
    save_entry(name, username, pw, url)
    try:
        _secure_copy(pw)
        _clear_later()
        extra = " ve panoya kopyalandı (30 sn)"
    except Exception:
        extra = ""
    return f"'{name}' için {length} karakterlik güçlü şifre oluşturuldu, kasaya kaydedildi{extra}."


def _clear_later():
    import threading

    def run():
        time.sleep(30)
        try:
            _secure_copy("")
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def password_check(name):
    """Kasadaki bir şifrenin gücünü değerlendirir (şifreyi göstermeden)."""
    pw = reveal(_find(name))
    score = sum([len(pw) >= 12, len(pw) >= 16, any(c.islower() for c in pw), any(c.isupper() for c in pw),
                 any(c.isdigit() for c in pw), any(not c.isalnum() for c in pw)])
    reused = sum(1 for k in _load() if k != name and reveal(k) == pw)
    return {"uzunluk": len(pw), "puan_6_üzerinden": score, "başka_hesapta_da_kullanılıyor": reused,
            "öneri": "Güçlü." if score >= 5 and not reused else "vault_generate ile yenisini oluştur."}


TOOLS = {
    "vault_list": (vault_list, _schema("Şifre kasasındaki kayıtların isimleri (şifreler gösterilmez)."), False),
    "vault_copy": (vault_copy, _schema("Kasadan şifreyi veya kullanıcı adını panoya kopyalar (şifre sana gösterilmez).",
                                       {"name": S("kayıt/site adı"), "field": {"type": "string", "enum": ["password", "username"]}}, ["name"]), True),
    "vault_type": (vault_type, _schema("Kasadan şifreyi/kullanıcı adını aktif giriş alanına yazar (giriş yapma için).",
                                       {"name": S("kayıt"), "field": {"type": "string", "enum": ["password", "username"]},
                                        "press_enter": {"type": "boolean"}}, ["name"]), True),
    "vault_generate": (vault_generate, _schema("Güçlü rastgele şifre üretip kasaya kaydeder.",
                                               {"name": S("kayıt adı"), "username": S("kullanıcı adı"), "length": N("uzunluk"), "url": S("site")}, ["name"]), False),
    "password_check": (password_check, _schema("Kasadaki şifrenin gücünü ve tekrar kullanımını kontrol eder.", {"name": S("kayıt")}, ["name"]), False),
}
