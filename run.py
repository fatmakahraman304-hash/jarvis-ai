"""JARVIS'i başlat.

  python run.py              -> sadece bu bilgisayar (http://127.0.0.1:8765)
  python run.py --lan        -> telefon da bağlanabilir (aynı Wi-Fi, erişim anahtarıyla)
  python run.py --lan --https -> şifreli bağlantı (VR gözlük, telefonda mikrofon/kamera için gerekli)
  python run.py --no-browser -> pencere açma
"""
import argparse
import asyncio
import os
import secrets
import socket
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _is_expected_proactor_reset(context):
    """Only recognize Windows peer-reset during Proactor socket cleanup."""
    exc = (context or {}).get("exception")
    if not isinstance(exc, ConnectionResetError):
        return False
    if getattr(exc, "winerror", None) != 10054 and getattr(exc, "errno", None) != 10054:
        return False
    handle = (context or {}).get("handle")
    callback = getattr(handle, "_callback", None)
    callback_name = getattr(callback, "__qualname__", "")
    message = str((context or {}).get("message", ""))
    return (
        callback_name.endswith("_call_connection_lost")
        or "_ProactorBasePipeTransport._call_connection_lost" in message
    )


def _install_windows_transport_handler():
    """Keep Proactor, but silence its known benign WinError 10054 cleanup callback."""
    if os.name != "nt":
        return
    base_policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if base_policy is None:
        return
    current = asyncio.get_event_loop_policy()
    if getattr(current, "_jarvis_reset_handler", False):
        return

    class JarvisProactorPolicy(base_policy):
        _jarvis_reset_handler = True

        def new_event_loop(self):
            loop = super().new_event_loop()

            def handle_exception(loop, context):
                if _is_expected_proactor_reset(context):
                    return
                loop.default_exception_handler(context)

            loop.set_exception_handler(handle_exception)
            return loop

    asyncio.set_event_loop_policy(JarvisProactorPolicy())

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def ensure_token():
    if os.environ.get("JARVIS_TOKEN", "").strip():
        return os.environ["JARVIS_TOKEN"].strip()
    env_file = ROOT / ".env"
    text = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    for line in text.splitlines():
        if line.startswith("JARVIS_TOKEN=") and line.split("=", 1)[1].strip():
            return line.split("=", 1)[1].strip()
    tok = secrets.token_urlsafe(12)
    lines = [ln for ln in text.splitlines() if not ln.startswith("JARVIS_TOKEN=")]
    lines.append(f"JARVIS_TOKEN={tok}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["JARVIS_TOKEN"] = tok
    return tok


def ensure_cert(ip):
    """Yerel ağ için kendinden imzalı sertifika (data/ssl). Tarayıcı ilk açılışta uyarı gösterir: 'Gelişmiş > Devam et'."""
    from datetime import datetime, timedelta, timezone
    import ipaddress
    d = Path(os.environ.get("JARVIS_DATA") or (ROOT / "data")) / "ssl"
    d.mkdir(parents=True, exist_ok=True)
    key_f, crt_f = d / "jarvis.key", d / "jarvis.crt"
    stamp = d / "ip.txt"
    if key_f.exists() and crt_f.exists() and stamp.exists() and stamp.read_text() == ip:
        return str(crt_f), str(key_f)
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "JARVIS yerel")])
    alt = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname()), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    try:
        alt.append(x509.IPAddress(ipaddress.ip_address(ip)))
    except ValueError:
        pass
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False).sign(key, hashes.SHA256()))
    key_f.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    crt_f.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    stamp.write_text(ip)
    return str(crt_f), str(key_f)


def open_window(url):
    time.sleep(1.5)
    if sys.platform.startswith("win"):
        candidates = [shutil.which("chrome")]
        for root in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if root:
                candidates.append(str(Path(root) / "Google/Chrome/Application/chrome.exe"))
        for exe in candidates:
            if exe and Path(exe).is_file():
                try:
                    subprocess.Popen([exe, "--app=" + url, "--window-size=1400,900"])
                    return
                except OSError:
                    continue
        print(f"Google Chrome bulunamadı. Chrome kur veya bu adresi Chrome’da aç: {url}")
        return
    webbrowser.open(url)


def supervise():
    """Gözetmen: JARVIS'i alt süreçte çalıştırır. Güncelleme sonrası (çıkış kodu 42) aynı pencerede kendiliğinden yeniden başlatır.
    Gözetmen kapatılırsa alt süreç de kapanır."""
    import signal
    args = sys.argv[1:]
    first = True
    child = {"p": None}

    def stop(*_):
        p = child["p"]
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(3)
            except Exception:
                p.kill()
        os._exit(0)
    for sig in ("SIGTERM", "SIGINT", "SIGBREAK", "SIGHUP"):
        if hasattr(signal, sig):
            try:
                signal.signal(getattr(signal, sig), stop)
            except Exception:
                pass
    while True:
        cmd = [sys.executable, str(ROOT / "run.py"), "--child", f"--parent={os.getpid()}"] + args + ([] if first or "--no-browser" in args else ["--no-browser"])
        child["p"] = subprocess.Popen(cmd)
        try:
            code = child["p"].wait()
        except KeyboardInterrupt:
            stop()
        if code == 42:
            first = False
            print("\n  [*] Güncelleme uygulandı, JARVIS yeniden başlatılıyor...\n")
            time.sleep(1)
            continue
        return code


def _watch_parent(pid):
    """Alt süreç: gözetmen beklenmedik şekilde ölürse kendini kapatır (sahipsiz kalmasın)."""
    def run():
        try:
            import psutil
        except ImportError:
            return
        while True:
            time.sleep(2)
            if not psutil.pid_exists(pid):
                os._exit(0)
    threading.Thread(target=run, daemon=True).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", action="store_true", help="telefondan erişim")
    ap.add_argument("--port", type=int, default=int(os.environ.get("JARVIS_PORT", 8765)))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--https", action="store_true", help="şifreli bağlantı (VR/AR, telefonda mikrofon ve kamera)")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--parent", type=int, default=0, help=argparse.SUPPRESS)
    ap.add_argument("--no-supervisor", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if not a.child and not a.no_supervisor:
        return supervise()
    if a.parent:
        _watch_parent(a.parent)

    host = "127.0.0.1"
    if a.lan:
        host = "0.0.0.0"
        tok = ensure_token()
    import uvicorn  # noqa: E402
    from core.config import VERSION  # noqa: E402

    ssl = {}
    scheme = "http"
    # LAN erişiminde kamera/mikrofon için güvenli bağlam zorunlu: --lan otomatik HTTPS kullanır.
    if a.https or a.lan:
        try:
            crt, key = ensure_cert(lan_ip())
            ssl = {"ssl_certfile": crt, "ssl_keyfile": key}
            scheme = "https"
        except ImportError as e:
            if a.lan or a.https:
                raise SystemExit("[HATA] Telefon kamerası için HTTPS gerekli. 'python -m pip install -r requirements.txt' çalıştırıp yeniden başlat.") from e
            print("  [!] HTTPS için 'pip install cryptography' gerekli.")
    url = f"{scheme}://127.0.0.1:{a.port}"
    print("=" * 60)
    print(f"  J.A.R.V.I.S. Personal AI v{VERSION}")
    print(f"  Bilgisayar : {url}")
    if a.lan:
        print(f"  Telefon    : {scheme}://{lan_ip()}:{a.port}/?token={tok}")
        if scheme == "https":
            print("  (İlk açılışta 'bağlantı gizli değil' uyarısı çıkar: Gelişmiş > Devam et. Sertifika bu bilgisayarda üretildi.)")
        print("  (Telefon aynı Wi-Fi'da olmalı. Bu adresi kimseyle paylaşma.)")
    print("  Kapatmak için bu pencerede Ctrl+C")
    print("=" * 60)
    if not a.no_browser:
        threading.Thread(target=open_window, args=(url,), daemon=True).start()
    _install_windows_transport_handler()
    uvicorn.run("core.server:app", host=host, port=a.port, log_level="warning", timeout_graceful_shutdown=2, **ssl)


if __name__ == "__main__":
    sys.exit(main() or 0)
