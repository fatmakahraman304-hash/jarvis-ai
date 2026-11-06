"""Canlı arama + anlamsal hafıza testi (gerçek internete çıkmaz, sahte cevaplarla).
Çalıştır: python tests/test_search.py"""
import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_srch_")
os.environ["GEMINI_API_KEY"] = "test"
from core import llm, tools  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


BING = '<li class="b_algo"><h2><a href="https://site.com/dolar">Dolar bugün</a></h2><p>Dolar 41,2 TL</p></li>'
RSS = ('<?xml version="1.0"?><rss><channel><item><title>Faiz kararı açıklandı</title><link>https://n.com/1</link>'
       '<pubDate>Thu, 05 Nov 2026 08:30:00 GMT</pubDate><source url="https://aa.com.tr">AA</source></item></channel></rss>')
state = {"bing_down": False, "lite_down": False, "ground": True, "ground_calls": 0}


def fake_get(url, timeout=12):
    if "bing.com" in url:
        if state["bing_down"]:
            raise RuntimeError("engellendi")
        return BING
    if "news.google.com" in url:
        return RSS
    if "lite.duckduckgo" in url:
        if state["lite_down"]:
            raise RuntimeError("Lite engellendi")
        return "<a rel=\"nofollow\" href=\"https://lite.com/x\" class='result-link'>Lite sonuç</a><td class='result-snippet'>özet</td>"
    raise RuntimeError("yok")


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


real_urlopen = tools.urllib.request.urlopen


def fake_urlopen(req, timeout=10):
    url = req.full_url if hasattr(req, "full_url") else req
    if "generateContent" in url:
        state["ground_calls"] += 1
        state["ground_url"] = url
        if not state["ground"]:
            raise urllib.error.HTTPError(url, 429, "quota", {}, io.BytesIO(b'{"error":"PerDay"}'))
        return Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": "5 Kasım 2026 itibarıyla dolar 41,2 TL."}]},
                                                "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://g.co/x", "title": "tcmb.gov.tr"}}]}}]}).encode())
    if "duckduckgo.com/html" in url:
        return Resp(b"<html>anomaly-modal</html>")
    raise urllib.error.URLError("yok")


tools._http_get = fake_get
tools.urllib.request.urlopen = fake_urlopen
llm.list_models = lambda pid, refresh=False: ["gemini-3.8-flash", "gemini-3.5-flash-lite"] if pid == "gemini" else []
llm.configured = lambda pid: pid == "gemini"

print("CANLI ARAMA")
r = tools.web_search("dolar kuru bugün")
check("ilk yararlı arama motoru hızlı döner", r.get("sonuçlar", [{}])[0].get("link") == "https://site.com/dolar", r)
check("normal web aramasında ikinci Gemini üretimi yapılmaz", state["ground_calls"] == 0, state["ground_calls"])
check("Bing sonuçları gelir", r.get("motor") == "bing" and r["sonuçlar"][0]["link"] == "https://site.com/dolar", r)
check("'bugün' geçince tarihli haberler de eklenir", r.get("haberler", [{}])[0].get("tarih", "").startswith("05.11.2026"), r)
check("CANLI sonuç notu korunur", "CANLI" in r.get("not", ""))
state.update(bing_down=True, ground=False)
r = tools.web_search("python nasıl kurulur")
check("Bing ve DuckDuckGo engellenince DuckDuckGo Lite'a düşer", r.get("motor") == "duckduckgo-lite" and r["sonuçlar"][0]["link"] == "https://lite.com/x", r)
check("Gemini kotası dolunca arama yine çalışır", "canlı_cevap" not in r)
n = state["ground_calls"]
tools.web_search("başka bir şey")
check("kotası dolan model web motoru sonuç verirken boşuna denenmez", state["ground_calls"] == n)

# Grounded Gemini is a fallback only when all ordinary web engines fail.
state.update(bing_down=True, lite_down=True, ground=True)
r = tools.web_search("son çare araması")
check("bütün web motorları başarısızsa Google Grounding yedeği çalışır",
      r.get("canlı_cevap", {}).get("cevap", "").startswith("5 Kasım 2026") and state["ground_calls"] == n + 1, r)
import time as _t  # noqa: E402
state.update(bing_down=False, lite_down=False, ground=True)
orig_get = tools._http_get


def slow_get(url, timeout=12):
    if "bing.com" in url:
        _t.sleep(4)
    return orig_get(url, timeout)


tools._http_get = slow_get
t0 = _t.time(); r = tools.web_search("yavaş kaynak testi")
check("takılan kaynak beklenmez: ilk işe yarar sonuç hızlı döner", _t.time() - t0 < 3 and ("sonuçlar" in r or "canlı_cevap" in r), round(_t.time() - t0, 1))
tools._http_get = orig_get
check("news_search aracı var ve tarihli", tools.TOOLS["news_search"][0]("faiz")[0]["kaynak"] == "AA")

print("ANLAMSAL HAFIZA")
from core.skills import semantic  # noqa: E402
calls = []


def fake_embed_urlopen(req, timeout=10):
    url, body = req.full_url, json.loads(req.data or b"{}")
    calls.append((url.rsplit("/", 1)[-1], body.get("model")))
    if url.endswith("/embeddings"):
        raise urllib.error.HTTPError(url, 400, "bad", {}, io.BytesIO(b'{"error":{"message":"model not supported"}}'))
    if "batchEmbedContents" in url:
        return Resp(json.dumps({"embeddings": [{"values": [0.1, 0.2]} for _ in body["requests"]]}).encode())
    raise urllib.error.URLError("x")


semantic.urllib.request.urlopen = fake_embed_urlopen
m, v = semantic.embed(["merhaba", "", "dünya"])
check("OpenAI katmanı 400 verince Gemini'nin kendi uç noktasıyla vektör üretir", m and len(v) == 3, calls)
calls.clear()
semantic.embed(["x"] * 40)
check("büyük istek küçük paketlere bölünür", sum(1 for c in calls if c[0].endswith("batchEmbedContents")) == 3, calls)

print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
