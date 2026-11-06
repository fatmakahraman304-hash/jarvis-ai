"""Uçtan uca test: sahte bir model sunucusu açar, gerçek JARVIS sunucusunu başlatır ve API'yi dener.

Çalıştır:  python tests/test_smoke.py
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read()


def post_sse(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    evs = []
    with urllib.request.urlopen(req, timeout=30) as r:
        for line in r:
            line = line.decode().strip()
            if line.startswith("data:"):
                evs.append(json.loads(line[5:]))
    return evs


def main():
    fport, jport = free_port(), free_port()
    env = dict(os.environ, CUSTOM_BASE_URL=f"http://127.0.0.1:{fport}", JARVIS_PORT=str(jport),
               GEMINI_API_KEY="", GROQ_API_KEY="", OPENROUTER_API_KEY="", XAI_API_KEY="",
               MISTRAL_API_KEY="", CEREBRAS_API_KEY="", TELEGRAM_BOT_TOKEN="",
               JARVIS_DATA=tempfile.mkdtemp(prefix="jarvis_smoke_"))
    fake = subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_llm.py"), str(fport)])
    srv = subprocess.Popen([sys.executable, str(ROOT / "run.py"), "--no-browser", "--port", str(jport)], env=env, cwd=ROOT)
    base = f"http://127.0.0.1:{jport}"
    ok = True
    try:
        for _ in range(450):  # Windows'ta ilk açılış (paket yüklemeleri) uzun sürebilir: 90 sn'ye kadar bekle
            try:
                get(base + "/api/state")
                break
            except Exception:
                time.sleep(0.2)

        def check(name, cond):
            nonlocal ok
            print(("  ✓ " if cond else "  ✗ ") + name)
            ok = ok and cond

        st = json.loads(get(base + "/api/state")[1])
        check("durum + 3 kişilik", len(st["personas"]) == 3)
        check("arayüz açılıyor", get(base + "/")[0] == 200)
        check("three.js gömülü", get(base + "/static/vendor/three.min.js")[0] == 200)
        evs = post_sse(base + "/api/chat", {"text": "saat kaç", "persona": "jarvis", "session": "test"})
        check("araç çağrısı (get_time)", any(e["type"] == "tool" and e["name"] == "get_time" for e in evs))
        check("akışlı cevap", any(e["type"] == "token" for e in evs) and evs[-1]["type"] == "done")
        evs = post_sse(base + "/api/chat", {"text": "dosyayı sil", "persona": "jarvis", "session": "test"})
        conf = [e for e in evs if e["type"] == "confirm"]
        check("kritik işlem onaya düştü", bool(conf))
        evs = post_sse(base + "/api/confirm", {"id": conf[0]["id"], "approve": False})
        check("onay reddedildi, beyin cevap verdi", evs[-1]["type"] == "done")
        sysd = json.loads(get(base + "/api/system")[1])
        check("sistem durumu", "cpu_yüzde" in sysd)
    finally:
        srv.terminate()
        fake.terminate()
    print("\nSONUÇ:", "BAŞARILI" if ok else "HATA VAR")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
