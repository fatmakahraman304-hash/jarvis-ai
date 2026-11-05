"""Test için sahte OpenAI uyumlu model sunucusu (gerçek API anahtarı olmadan uçtan uca test)."""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _chunk(self, obj):
        self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
        self.wfile.flush()

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/embeddings"):  # kelime-karma vektörleri (deterministik)
            import hashlib as _h
            import re as _r
            inp = req["input"] if isinstance(req["input"], list) else [req["input"]]
            def vec(t):
                v = [0.0] * 64
                for w in _r.findall(r"\w{3,}", t.lower()):
                    v[int(_h.md5(w[:6].encode()).hexdigest(), 16) % 64] += 1
                return v
            body = json.dumps({"data": [{"index": i, "embedding": vec(t)} for i, t in enumerate(inp)]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        msgs = req["messages"]
        last = msgs[-1]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
        sysm = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""
        if isinstance(user, str) and "ekip yöneticisisin" in sysm:
            plan = [{"id": 1, "role": "araştırmacı", "task": "Konuyu araştır", "depends_on": []},
                    {"id": 2, "role": "analist", "task": "Verileri analiz et", "depends_on": []},
                    {"id": 3, "role": "yazar", "task": "Raporu yaz", "depends_on": [1, 2]}]
            self._chunk({"choices": [{"delta": {"content": "Plan: " + json.dumps(plan, ensure_ascii=False)}}]})
            self.wfile.write(b"data: [DONE]\n\n"); return
        if isinstance(user, str) and "tercümansın" in sysm:
            import re as _re
            body = user.split("<<<\n", 1)[-1].rsplit("\n>>>", 1)[0]
            dil = _re.search(r"metni (\S+) diline", user).group(1)
            if "Her satırı ayrı" in body:
                out = "\n".join(f"{m.group(1)}|[{dil}] {m.group(2)}" for m in _re.finditer(r"^(\d+)\|(.*)$", body, _re.M))
            else:
                out = f"[{dil}] {body}"
            self._chunk({"choices": [{"delta": {"content": out}}]})
            self.wfile.write(b"data: [DONE]\n\n"); return
        canned = None
        if isinstance(user, str) and "öğretmensin" in sysm:
            canned = json.dumps([{"q": "Fotosentez nerede olur?", "options": ["Kloroplast", "Mitokondri", "Çekirdek", "Ribozom"], "answer": 0, "explain": "Kloroplastta."},
                                 {"q": "Fotosentezin ürünü?", "options": ["CO2", "Glikoz", "Azot", "Su"], "answer": 1, "explain": "Glikoz ve O2."},
                                 {"q": "bozuk", "options": ["a"], "answer": 5}], ensure_ascii=False)
        elif isinstance(user, str) and "eğitim koçusun" in sysm:
            canned = json.dumps({"weeks": [{"week": 1, "focus": "Temeller", "tasks": ["Sözdizimi", "Değişkenler"], "resources": ["Belgeler"], "check": "mini proje"},
                                           {"week": 2, "focus": "Fonksiyonlar", "tasks": ["Fonksiyon yaz"], "resources": [], "check": "quiz"}]}, ensure_ascii=False)
        elif isinstance(user, str) and "rafiği çıkaran" in sysm:
            canned = json.dumps({"nodes": [{"id": "Ankara", "type": "yer"}, {"id": "Atatürk", "type": "kişi"}, {"id": "Cumhuriyet", "type": "kavram"}, {"id": "Hayalet", "type": "kavram"}],
                                 "edges": [{"a": "Atatürk", "b": "Cumhuriyet", "rel": "kurdu"}, {"a": "Cumhuriyet", "b": "Ankara", "rel": "başkenti"}, {"a": "X", "b": "Ankara", "rel": "geçersiz"}]}, ensure_ascii=False)
        elif isinstance(user, str) and "araştırma asistanısın" in sysm:
            canned = "Kaynağa göre cevap [1]. KAYNAK_SAYISI=" + str(user.count("» s."))
        if canned is not None:
            self._chunk({"choices": [{"delta": {"content": canned}}]})
            self.wfile.write(b"data: [DONE]\n\n"); return
        if isinstance(user, str) and "titiz bir denetçisin" in sysm:
            self._chunk({"choices": [{"delta": {"content": json.dumps({"sorunlu": [{"id": 2, "neden": "sayılar kaynaksız"}], "genel": "2. görev eksik"}, ensure_ascii=False)}}]})
            self.wfile.write(b"data: [DONE]\n\n"); return
        if isinstance(user, str) and "ALT GÖREV #" in user:
            self._chunk({"choices": [{"delta": {"content": "RAPOR " + user.split("ALT GÖREV ")[1][:3] + (" girdi:" + ",".join(sorted(set(__import__("re").findall(r"\[#(\d)", user)))) if "[#" in user else "") + (" düzeltildi" if "DENETÇİ" in user else "")}}]})
            self.wfile.write(b"data: [DONE]\n\n"); return
        if last["role"] == "user" and "saat" in user and req.get("tools"):
            self._chunk({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "get_time", "arguments": ""}}]}}]})
            self._chunk({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{}"}}]}}]})
        elif last["role"] == "user" and "sil" in user and req.get("tools"):
            self._chunk({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c2", "function": {"name": "delete_file", "arguments": "{\"path\": \"/tmp/x.txt\"}"}}]}}]})
        else:
            sysmsg = msgs[0]["content"][:30]
            for w in ["Tamam ", "efendim, ", f"son mesaj rolü {last['role']}. ", f"[{sysmsg}]"]:
                self._chunk({"choices": [{"delta": {"content": w}}]})
        self.wfile.write(b"data: [DONE]\n\n")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
