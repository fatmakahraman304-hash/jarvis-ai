"""Çoklu model katmanı.

Bütün sağlayıcılar OpenAI uyumlu /chat/completions arayüzüyle konuşur:
Gemini, Groq, OpenRouter (ücretsiz modeller), xAI Grok, Mistral, Cerebras, Ollama (yerel)
ve isteğe bağlı herhangi bir OpenAI uyumlu sunucu.

Ek kütüphane gerektirmez (urllib). Model adları her açılışta sağlayıcının
/models listesinden otomatik seçilir; böylece model isimleri değişse de çalışır.
"""
import json
import socket
import threading
import time
import urllib.error
import urllib.request

from .config import env

UA = "JarvisPersonalAI/1.0"

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
        "prefer": ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
        # arka plan işleri (brifing, özet, çeviri…) için: ücretsiz kotası geniş hafif modeller → 3.8'in günlük hakkı sohbete kalır
        "light": ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"],
        "free": True,
    },
    "groq": {
        "label": "Groq (Llama / GPT-OSS)",
        "base": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        # en güçlü ücretsiz: GPT-OSS 120B (akıl yürütme + araç kullanımı, günde 1000 istek); sonra Qwen 3.8, Llama 3.3 70B
        "prefer": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-8b-instant"],
        "light": ["openai/gpt-oss-20b", "llama-3.1-8b-instant"],
        "free": True,
    },
    "openrouter": {
        "label": "OpenRouter (ücretsiz modeller)",
        "base": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "prefer": ["deepseek/deepseek-chat-v3-0324:free", "meta-llama/llama-3.3-70b-instruct:free", "qwen/qwen3-235b-a22b:free"],
        "only_free_suffix": ":free",
        "free": True,
    },
    "xai": {
        "label": "xAI Grok",
        "base": "https://api.x.ai/v1",
        "key_env": "XAI_API_KEY",
        "prefer": ["grok-4-fast", "grok-4-fast-non-reasoning", "grok-3-mini", "grok-3"],
        "free": False,
    },
    "mistral": {
        "label": "Mistral",
        "base": "https://api.mistral.ai/v1",
        "key_env": "MISTRAL_API_KEY",
        "prefer": ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"],
        "free": True,
    },
    "cerebras": {
        "label": "Cerebras",
        "base": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "prefer": ["llama-3.3-70b", "gpt-oss-120b", "qwen-3-32b", "llama3.1-8b"],
        "free": True,
    },
    "ollama": {
        "label": "Ollama (yerel, internetsiz)",
        "base": "http://localhost:11434/v1",
        "key_env": "",
        "prefer": ["qwen2.5", "llama3.1", "llama3.2", "gemma3", "mistral"],
        "free": True,
    },
    "custom": {
        "label": "Özel OpenAI uyumlu sunucu",
        "base": "",
        "key_env": "CUSTOM_API_KEY",
        "prefer": [],
        "free": True,
    },
}


class ProviderError(Exception):
    def __init__(self, provider, status, body):
        super().__init__(f"{provider} HTTP {status}: {body[:300]}")
        self.provider = provider
        self.status = status
        self.body = body or ""


def _base(pid):
    if pid == "custom":
        return env("CUSTOM_BASE_URL").rstrip("/")
    if pid == "ollama":
        return env("OLLAMA_BASE_URL", PROVIDERS["ollama"]["base"]).rstrip("/")
    return PROVIDERS[pid]["base"]


def _key(pid):
    k = PROVIDERS[pid]["key_env"]
    return env(k) if k else ""


def _headers(pid):
    h = {"Content-Type": "application/json", "User-Agent": UA}
    key = _key(pid)
    if key:
        h["Authorization"] = f"Bearer {key}"
    if pid == "openrouter":
        h["HTTP-Referer"] = "http://localhost"
        h["X-Title"] = "JARVIS Personal AI"
    return h


def _ollama_up():
    base = _base("ollama")
    try:
        host = base.split("://", 1)[1].split("/", 1)[0]
        h, _, p = host.partition(":")
        with socket.create_connection((h, int(p or 80)), timeout=0.4):
            return True
    except Exception:
        return False


def configured(pid):
    if pid == "ollama":
        return _ollama_up()
    if pid == "custom":
        return bool(_base("custom"))
    return bool(_key(pid))


# ---------------- model listesi ----------------
_model_cache = {}
_cache_lock = threading.Lock()


def list_models(pid, refresh=False):
    with _cache_lock:
        if not refresh and pid in _model_cache and time.time() - _model_cache[pid][0] < 3600:
            return _model_cache[pid][1]
    models = []
    try:
        req = urllib.request.Request(_base(pid) + "/models", headers=_headers(pid))
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for m in data.get("data", data.get("models", [])):
            mid = m.get("id") or m.get("name") or ""
            if mid.startswith("models/"):
                mid = mid[len("models/"):]
            if mid:
                models.append(mid)
    except Exception:
        models = []
    suffix = PROVIDERS[pid].get("only_free_suffix")
    if suffix and models:
        models = [m for m in models if m.endswith(suffix)] or models
    with _cache_lock:
        _model_cache[pid] = (time.time(), models)
    return models


# sohbet modeli OLMAYANLAR (aynı adla başlayan ses/canlı/görsel sürümleri yanlışlıkla seçilmesin)
NON_CHAT = ("embed", "tts", "image", "whisper", "guard", "vision-preview", "aqa", "live", "transcribe", "robotics",
            "omni", "banana", "lyria", "veo", "imagen", "audio", "native-audio", "computer-use", "orpheus", "playai", "distil-whisper")


def is_chat_model(m):
    return not any(x in m for x in NON_CHAT)


def ranked_models(pid):
    """Tercih sırasına göre bu hesapta GERÇEKTEN açık olan sohbet modelleri (en iyisi başta)."""
    prefer = PROVIDERS[pid]["prefer"]
    available = [m for m in list_models(pid) if is_chat_model(m)]
    out = []
    for p in prefer:
        for m in available:  # önce birebir ad, sonra aynı ailenin tarihli sürümleri (gemini-3.8-flash-001 gibi)
            if m == p and m not in out:
                out.append(m)
        for m in available:
            if m not in out and (m.startswith(p + ":") or m.startswith(p + "-")) and ("lite" in p or "lite" not in m):
                out.append(m)
    return out + [m for m in available if m not in out]


# ---- ücretsiz kota takibi: kotası dolan model, kota yenilenene kadar atlanır (her mesajda boşuna denenmez) ----
_cooldown = {}  # (pid, model) -> bu zamana kadar kullanma


def _quota_reset_ts():
    """Google ücretsiz günlük kotası Pasifik gece yarısı yenilenir (~08:00 UTC)."""
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    nxt = now.replace(hour=8, minute=5, second=0, microsecond=0)
    if nxt <= now:
        nxt += _dt.timedelta(days=1)
    return nxt.timestamp()


def mark_exhausted(pid, model, body=""):
    b = (body or "").lower()
    daily = any(x in b for x in ("perday", "per day", "per_day", "requests per day", "rpd", "daily"))
    _cooldown[(pid, model)] = _quota_reset_ts() if daily else time.time() + 65
    return daily


def cooling(pid, model):
    t = _cooldown.get((pid, model), 0)
    if t and t > time.time():
        return t
    _cooldown.pop((pid, model), None)
    return 0


def pick_model(pid, override=""):
    if override:
        return override
    envm = env(f"{pid.upper()}_MODEL")
    if envm:
        return envm
    prefer = PROVIDERS[pid]["prefer"]
    if list_models(pid):
        r = ranked_models(pid)
        ready = [m for m in r if not cooling(pid, m)]
        return (ready or r or list_models(pid))[0]
    ready = [m for m in prefer if not cooling(pid, m)]
    return (ready or prefer or [""])[0]


def next_model(pid, current, tried):
    """Model kota/erişim hatası verirse AYNI sağlayıcıda bir sonraki en iyi model."""
    for m in ranked_models(pid) or PROVIDERS[pid]["prefer"]:
        if m != current and m not in tried and not cooling(pid, m):
            return m
    return ""


def status():
    out = []
    for pid, p in PROVIDERS.items():
        out.append({
            "id": pid,
            "label": p["label"],
            "configured": configured(pid),
            "free": p["free"],
            "key_env": p["key_env"],
        })
    return out


class ThinkFilter:
    """Qwen/DeepSeek gibi modellerin <think>…</think> iç düşüncesini cevaptan ayıklar (parçalı akışta da)."""
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.buf, self.inside = "", False

    def feed(self, piece):
        self.buf += piece
        out = ""
        while True:
            if not self.inside:
                i = self.buf.find(self.OPEN)
                if i >= 0:
                    out += self.buf[:i]
                    self.buf, self.inside = self.buf[i + len(self.OPEN):], True
                    continue
                keep = 0  # etiketin yarısı bu parçada kalmış olabilir
                for k in range(min(len(self.OPEN) - 1, len(self.buf)), 0, -1):
                    if self.OPEN.startswith(self.buf[-k:]):
                        keep = k
                        break
                out += self.buf[:len(self.buf) - keep]
                self.buf = self.buf[len(self.buf) - keep:]
                return out
            j = self.buf.find(self.CLOSE)
            if j < 0:
                self.buf = self.buf[-(len(self.CLOSE) - 1):]
                return out
            self.buf, self.inside = self.buf[j + len(self.CLOSE):].lstrip("\n"), False

    def flush(self):
        rest, self.buf = ("" if self.inside else self.buf), ""
        return rest


# ---------------- akışlı sohbet ----------------
def stream_chat(pid, model, messages, tools=None, temperature=0.7, timeout=90):
    """Olay üretir: ("text", parça) ... ve sonda ("final", {"content":..., "tool_calls":[...]})"""
    body = {"model": model, "messages": messages, "stream": True, "temperature": temperature}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        _base(pid) + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=_headers(pid),
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        try:
            txt = e.read().decode("utf-8", "ignore")
        except Exception:
            txt = ""
        raise ProviderError(pid, e.code, txt)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderError(pid, 0, str(e))

    content = []
    calls = {}
    think = ThinkFilter()
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except Exception:
                continue
            if chunk.get("error"):
                raise ProviderError(pid, 500, json.dumps(chunk["error"]))
            for ch in chunk.get("choices", []):
                delta = ch.get("delta") or ch.get("message") or {}
                piece = delta.get("content")
                if piece:
                    piece = think.feed(piece)
                if piece:
                    content.append(piece)
                    yield ("text", piece)
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", len(calls))
                    slot = calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        a = fn["arguments"]
                        slot["arguments"] += a if isinstance(a, str) else json.dumps(a)
    tail = think.flush()
    if tail:
        content.append(tail)
        yield ("text", tail)
    tool_calls = []
    for i in sorted(calls):
        c = calls[i]
        if not c["name"]:
            continue
        tool_calls.append({
            "id": c["id"] or f"call_{i}_{int(time.time()*1000)}",
            "type": "function",
            "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
        })
    yield ("final", {"content": "".join(content), "tool_calls": tool_calls})


VISION_ORDER = ["gemini", "openrouter", "xai", "groq", "mistral", "ollama", "custom"]
VISION_DEFAULTS = {"groq": "meta-llama/llama-4-scout-17b-16e-instruct", "mistral": "pixtral-12b-latest",
                   "openrouter": "google/gemma-3-27b-it:free", "ollama": "llava"}


def vision(prompt, image_bytes, mime="image/png", system=""):
    """Görüntüyü görebilen ilk modele sorar. Metin cevabı döner."""
    import base64
    url = f"data:{mime};base64," + base64.b64encode(image_bytes).decode()
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": [{"type": "text", "text": prompt},
                                             {"type": "image_url", "image_url": {"url": url}}]})
    errors = []
    for pid in VISION_ORDER:
        if not configured(pid):
            continue
        model = env(f"{pid.upper()}_VISION_MODEL") or (pick_model(pid) if pid in ("gemini", "xai", "custom") else VISION_DEFAULTS.get(pid, ""))
        if not model:
            continue
        try:
            text = ""
            for kind, data in stream_chat(pid, model, msgs, None, temperature=0.2):
                if kind == "text":
                    text += data
            if text.strip():
                return text.strip()
        except ProviderError as e:
            errors.append(f"{pid}: {e.status}")
    raise RuntimeError("Görüntü analizi yapabilen model yok (Gemini önerilir). " + ", ".join(errors))


def _tools_unsupported(err):
    b = err.body.lower()
    return err.status in (400, 404, 422) and ("tool" in b or "function" in b)


def light_model(pid):
    if env(f"{pid.upper()}_MODEL") or not PROVIDERS[pid].get("light"):
        return ""
    avail = set(list_models(pid))
    for m in PROVIDERS[pid]["light"]:
        if (m in avail or not avail) and not cooling(pid, m):
            return m
    return ""


def route(order, messages, tools, model_override="", light=False):
    """Sağlayıcıları sırayla dener; kota/hata olursa sıradakine geçer (tek beyin, çok model).

    Olay üretir: ("provider", {...}), ("text", parça), ("final", {...}), ("error", metin)
    """
    tried = []
    candidates = [p for p in order if p in PROVIDERS] + [p for p in PROVIDERS if p not in order]
    candidates = [p for p in candidates if configured(p)]
    if not candidates:
        yield ("error", "NO_PROVIDER")
        return
    for i, pid in enumerate(candidates):
        model = pick_model(pid, model_override if i == 0 else "")
        if light and not (model_override and i == 0):
            model = light_model(pid) or model
        if not model:
            continue
        use_tools = tools
        used = []
        for attempt in range(5):
            emitted = False
            try:
                yield ("provider", {"provider": pid, "model": model, "label": PROVIDERS[pid]["label"]})
                for ev in stream_chat(pid, model, messages, use_tools):
                    if ev[0] == "text":
                        emitted = True
                    yield ev
                return
            except ProviderError as e:
                tried.append(f"{pid}: {e.status}")
                if emitted:
                    yield ("text", "\n[bağlantı kesildi]")
                    yield ("final", {"content": "", "tool_calls": []})
                    return
                if use_tools and _tools_unsupported(e) and attempt == 0:
                    use_tools = None
                    continue
                if e.status == 404 and attempt == 0:
                    list_models(pid, refresh=True)  # model adı eskimiş olabilir: listeyi yenile
                if e.status == 429:
                    mark_exhausted(pid, model, e.body)
                if e.status in (403, 404, 429) and len(used) < 3:
                    # bu model kotada/erişilemez: aynı sağlayıcının bir sonraki en iyi modeline geç (ör. 3.8 → 3.6)
                    nm = next_model(pid, model, used)
                    if nm:
                        used.append(model)
                        model = nm
                        continue
                break
    yield ("error", "Tüm modeller başarısız: " + ", ".join(tried))
