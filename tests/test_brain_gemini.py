"""Uçtan uca beyin testi (sahte Gemini sunucusu, gerçek brain.chat + araçlar): selamlaşma anında cevaplanır, araçlı soru
araç sonucuyla cevaplanır, takılan model beklenmeden sıradaki modele geçilir, aynı aracı döngüyle çağırma kırılır.
Çalıştır: python tests/test_brain_gemini.py"""
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_bg_")
os.environ["GEMINI_API_KEY"] = "AQ.Ab8RN6Kq_test_key_0123456789abcdefghijklmnop"
for k in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_MODEL", "CUSTOM_BASE_URL"):
    os.environ.pop(k, None)

from core import brain, gemini_native, llm, tools  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


MODE = {"m": "hello"}
CALLS = []


class G(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"models": [{"name": "models/gemini-3.8-flash"}, {"name": "models/gemini-3.6-flash"}, {"name": "models/gemini-3.5-flash-lite"}]}).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = self.path.split("/models/")[1].split(":")[0]
        CALLS.append(model)
        has_resp = any("functionResponse" in p for c in body["contents"] for p in c["parts"])
        if MODE["m"] == "hang" and model == "gemini-3.8-flash":
            time.sleep(4)
        if MODE["m"] in ("tool", "loop") and body.get("tools") and (not has_resp or MODE["m"] == "loop"):
            parts = [{"functionCall": {"name": "get_time", "args": {}}, "thoughtSignature": "S"}]
        else:
            parts = [{"text": "Merhaba efendim." if not has_resp else "Saat bilgisini aldım efendim."}]
        try:
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({"candidates": [{"content": {"role": "model", "parts": parts}}]}).encode())
        except Exception:
            pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), G)
threading.Thread(target=srv.serve_forever, daemon=True).start()
gemini_native.ROOT = f"http://127.0.0.1:{srv.server_address[1]}/v1beta"
llm.list_models("gemini", refresh=True)

print("BEYİN + GEMİNİ")
t0 = time.time(); txt, _, meta = brain.collect(brain.chat("Merhaba", "friday", session="t1"))
check("'Merhaba' hemen cevaplanır", txt == "Merhaba efendim." and time.time() - t0 < 5, (txt, round(time.time() - t0, 1)))
MODE["m"] = "tool"; CALLS.clear()
txt, _, _ = brain.collect(brain.chat("saat kaç", "friday", session="t2"))
check("araç çağrılır, sonucu ile cevap verilir", txt == "Saat bilgisini aldım efendim." and len(CALLS) == 2, (txt, CALLS))
MODE["m"] = "hang"; CALLS.clear(); gemini_native.TIMEOUT = 2
t0 = time.time(); txt, _, meta = brain.collect(brain.chat("Merhaba", "friday", session="t3"))
check("takılan 3.8 beklenmez → 3.6 cevap verir", txt == "Merhaba efendim." and "gemini-3.6-flash" in CALLS and time.time() - t0 < 8, (txt, CALLS, round(time.time() - t0, 1)))
gemini_native.TIMEOUT = 45; llm._cooldown.clear()
MODE["m"] = "loop"; CALLS.clear()
t0 = time.time(); txt, _, _ = brain.collect(brain.chat("saat kaç", "friday", session="t4"))
check("aynı aracı sonsuz çağırma döngüsü kırılır, yine de cevap gelir", bool(txt) and len(CALLS) <= brain.MAX_STEPS + 1 and time.time() - t0 < 20, (txt, len(CALLS)))

srv.shutdown()
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
