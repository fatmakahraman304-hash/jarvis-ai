"""Gemini kendi uç noktası testi (sahte Google sunucusu): yeni 'AQ.' anahtar x-goog-api-key ile gider (Bearer YOK),
akışlı metin, araç çağrısı + thoughtSignature'ın bir sonraki adımda geri gönderilmesi, şema sadeleştirme, model listesi.
Çalıştır: python tests/test_gemini.py"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_gem_")
KEY = "AQ.Ab8RN6Kq_test_key_0123456789abcdefghijklmnop"
os.environ["GEMINI_API_KEY"] = KEY
for k in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_MODEL"):
    os.environ.pop(k, None)

from core import gemini_native, llm  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


SEEN = []


class G(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _auth_ok(self):
        return self.headers.get("x-goog-api-key") == KEY and not self.headers.get("Authorization")

    def do_GET(self):
        SEEN.append(("GET", self.path, dict(self.headers)))
        if not self._auth_ok():
            self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":{"code":400,"message":"API key not valid. Please pass a valid API key."}}'); return
        b = json.dumps({"models": [{"name": "models/gemini-3.8-flash"}, {"name": "models/gemini-3.8-flash-tts"}, {"name": "models/gemini-3.5-flash-lite"},
                                   {"name": "models/gemini-embedding-001"}]}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(("POST", self.path, dict(self.headers), body))
        if not self._auth_ok():
            self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":{"code":400,"message":"API key not valid. Please pass a valid API key."}}'); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        has_resp = any("functionResponse" in p for c in body["contents"] for p in c["parts"])
        if body.get("tools") and not has_resp:
            ev = [{"candidates": [{"content": {"role": "model", "parts": [{"text": "düşünce", "thought": True},
                   {"functionCall": {"name": "web_search", "args": {"query": "dolar kuru"}}, "thoughtSignature": "SIG123"}]}}]}]
        else:
            ev = [{"candidates": [{"content": {"parts": [{"text": "Dolar "}]}}]}, {"candidates": [{"content": {"parts": [{"text": "41,2 TL."}]}}]}]
        for e in ev:
            self.wfile.write(("data: " + json.dumps(e) + "\r\n\r\n").encode())


srv = ThreadingHTTPServer(("127.0.0.1", 0), G)
threading.Thread(target=srv.serve_forever, daemon=True).start()
gemini_native.ROOT = f"http://127.0.0.1:{srv.server_address[1]}/v1beta"

print("GEMİNİ (KENDİ UÇ NOKTASI)")
ms = llm.list_models("gemini", refresh=True)
check("AQ. anahtarla model listesi alınır", "gemini-3.8-flash" in ms, ms)
g = [s for s in SEEN if s[0] == "GET"][-1]
hd = {k.lower(): v for k, v in g[2].items()}
check("anahtar x-goog-api-key başlığıyla gider, Bearer gönderilmez", hd.get("x-goog-api-key") == KEY and "authorization" not in hd, hd)
check("otomatik model = gemini-3.8-flash", llm.pick_model("gemini") == "gemini-3.8-flash")

tools = [{"type": "function", "function": {"name": "web_search", "description": "ara", "parameters": {"type": "object", "properties": {
    "query": {"type": "string", "description": "q"}, "recent": {"type": ["boolean", "null"], "additionalProperties": False}}, "required": ["query", "yok"]}}},
         {"type": "function", "function": {"name": "get_time", "description": "saat", "parameters": {"type": "object", "properties": {}}}}]
msgs = [{"role": "system", "content": "Sen JARVIS'sin."}, {"role": "user", "content": "dolar kaç"}]
evs = list(llm.stream_chat("gemini", "gemini-3.8-flash", msgs, tools))
final = evs[-1][1]
post = [s for s in SEEN if s[0] == "POST"][-1]
check("sistem talimatı systemInstruction'a gider", post[3]["systemInstruction"]["parts"][0]["text"] == "Sen JARVIS'sin.")
decl = {d["name"]: d for d in post[3]["tools"][0]["functionDeclarations"]}
check("şema sadeleşir (desteklenmeyen alanlar/boş nesne atılır)", "parameters" not in decl["get_time"] and decl["web_search"]["parameters"]["properties"]["recent"] == {"type": "boolean"}
      and decl["web_search"]["parameters"]["required"] == ["query"], decl)
check("iç düşünce metni kullanıcıya gösterilmez", not any(k == "text" for k, _ in evs[:-1]))
tc = final["tool_calls"][0] if final["tool_calls"] else {}
check("araç çağrısı OpenAI biçimine döner + imza saklanır", tc.get("function", {}).get("name") == "web_search" and json.loads(tc["function"]["arguments"]) == {"query": "dolar kuru"}
      and tc.get("thought_signature") == "SIG123", final)
msgs += [{"role": "assistant", "content": "", "tool_calls": final["tool_calls"]},
         {"role": "tool", "tool_call_id": tc.get("id"), "name": "web_search", "content": '{"sonuç": "41,2"}'}]
evs = list(llm.stream_chat("gemini", "gemini-3.8-flash", msgs, tools))
post = [s for s in SEEN if s[0] == "POST"][-1][3]
model_turn = [c for c in post["contents"] if c["role"] == "model"][0]
check("ikinci adımda thoughtSignature Gemini'ye geri gönderilir", model_turn["parts"][0].get("thoughtSignature") == "SIG123")
check("araç sonucu functionResponse olarak gider", post["contents"][-1]["parts"][0]["functionResponse"] == {"name": "web_search", "response": {"sonuç": "41,2"}})
check("akışlı cevap birleşir", "".join(d for k, d in evs if k == "text") == "Dolar 41,2 TL." and evs[-1][1]["content"] == "Dolar 41,2 TL.")
r = "".join(d for k, d in llm.route(["gemini"], [{"role": "user", "content": "selam"}], None) if k == "text")
check("tam yol (route) yeni anahtarla çalışır", r == "Dolar 41,2 TL.", r)
check("AQ. anahtar biçimi 'doğru' sayılır", "Sorun:" not in llm.key_diagnosis("gemini"), llm.key_diagnosis("gemini"))
os.environ["GEMINI_API_KEY"] = "AQ.yanlis"
llm.list_models("gemini", refresh=True)
check("gerçekten yanlış anahtar yine teşhis edilir", "çok kısa" in (llm.key_bad("gemini") or ""), llm.key_bad("gemini"))

print("SES → YAZI (GEMİNİ)")
os.environ["GEMINI_API_KEY"] = KEY; llm.clear_key_state(); llm.list_models("gemini", refresh=True)
G.stt_reply = "BOŞ"
orig_post = G.do_POST


def stt_post(self):
    if ":generateContent" in self.path:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(("STT", self.path, dict(self.headers), body))
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"candidates": [{"content": {"parts": [{"text": G.stt_reply}]}}]}).encode()); return
    orig_post(self)


G.do_POST = stt_post
from core.skills.media import transcribe_bytes  # noqa: E402
info = {}
G.stt_reply = "Bugün hava nasıl?"
t = transcribe_bytes(b"RIFF" + b"\0" * 4000, "ses.wav", "audio/wav", "tr", info)
st = [s for s in SEEN if s[0] == "STT"][-1]
check("sesli komut Gemini ile yazıya döner", t == "Bugün hava nasıl?" and info["engine"] == "Gemini", (t, info))
check("ses kaydı WAV olarak, hafif modelle gider", st[3]["contents"][0]["parts"][0]["inline_data"]["mime_type"] == "audio/wav" and "flash-lite" in st[1], st[1])
G.stt_reply = "BOŞ."
check("sessizlikte uydurma yok (BOŞ → boş)", transcribe_bytes(b"RIFF" + b"\0" * 4000, "ses.wav", "audio/wav") == "")

srv.shutdown()
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
