"""Gemini'ye Google'ın KENDİ uç noktasıyla bağlanır (generativelanguage.googleapis.com/v1beta, x-goog-api-key).

Neden: 2026'da AI Studio yeni anahtarları 'AQ.' ile üretiyor; bunlar OpenAI uyumlu katmanda 'Authorization: Bearer'
ile reddediliyor ("API key not valid" / ACCESS_TOKEN_TYPE_UNSUPPORTED). Kendi uç noktası hem eski 'AIza' hem yeni
'AQ.' anahtarlarla çalışır. Bu modül JARVIS'in OpenAI biçimli mesaj/araç akışını Gemini biçimine çevirir ve geri çevirir;
Gemini 3'ün araç çağrısı 'thoughtSignature' imzalarını da korur (yoksa çok adımlı araç kullanımı 400 verir).
"""
import json
import copy
import time
import urllib.error
import urllib.request

ROOT = "https://generativelanguage.googleapis.com/v1beta"
_KEEP = {"type", "description", "properties", "required", "items", "enum", "format", "nullable", "minimum", "maximum"}


def headers(key):
    return {"Content-Type": "application/json", "x-goog-api-key": key, "User-Agent": "JarvisPersonalAI/1.0"}


def list_models(key, timeout=8):
    out, token = [], ""
    for _ in range(5):
        url = f"{ROOT}/models?pageSize=1000" + (f"&pageToken={token}" if token else "")
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers(key)), timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for m in data.get("models", []):
            name = (m.get("name") or "").removeprefix("models/")
            if name:
                out.append(name)
        token = data.get("nextPageToken") or ""
        if not token:
            break
    return out


def _schema(s):
    """JSON şemasını Gemini'nin kabul ettiği alt kümeye indirger."""
    if not isinstance(s, dict):
        return s
    out = {}
    for k, v in s.items():
        if k not in _KEEP:
            continue
        if k == "properties":
            v = {pk: _schema(pv) for pk, pv in (v or {}).items()}
        elif k == "items":
            v = _schema(v)
        elif k == "enum":
            # Gemini rejects empty enum entries even in an optional tool field.
            v = [x for x in v if x is not None and (not isinstance(x, str) or x.strip())] if isinstance(v, list) else v
            if not v:
                continue
        elif k == "type" and isinstance(v, list):  # ["string","null"] → string
            v = next((t for t in v if t != "null"), "string")
        out[k] = v
    if out.get("type") == "object" and not out.get("properties"):
        out.pop("properties", None)
        out.pop("required", None)
    if "required" in out and "properties" in out:
        out["required"] = [r for r in out["required"] if r in out["properties"]]
        if not out["required"]:
            out.pop("required")
    return out


def _tools(tools):
    decls = []
    for t in tools or []:
        f = t.get("function") or t
        d = {"name": f["name"], "description": (f.get("description") or "")[:1000]}
        params = _schema(f.get("parameters") or {})
        if params.get("properties"):
            d["parameters"] = params
        decls.append(d)
    return [{"functionDeclarations": decls}] if decls else None


def _user_parts(content):
    if isinstance(content, str):
        return [{"text": content or " "}]
    parts = []
    for c in content or []:
        if c.get("type") == "text":
            parts.append({"text": c.get("text") or " "})
        elif c.get("type") == "image_url":
            url = (c.get("image_url") or {}).get("url", "")
            if url.startswith("data:") and ";base64," in url:
                mime, b64 = url[5:].split(";base64,", 1)
                parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    return parts or [{"text": " "}]


def convert(messages, model=None):
    """OpenAI mesajları → (systemInstruction, contents)."""
    system, contents = [], []

    def add(role, parts):
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": list(parts)})

    names, native_ids, flattened = {}, {}, set()
    for m in messages:
        role = m.get("role")
        if role == "system":
            system.append(m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"), ensure_ascii=False))
        elif role == "user":
            add("user", _user_parts(m.get("content")))
        elif role == "assistant":
            foreign = bool(model and m.get("tool_provider") and (m["tool_provider"] != "gemini" or (m.get("tool_model") and m["tool_model"] != model)))
            if foreign and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    flattened.add(tc.get("id"))
                add("model", [{"text": "Önceki modelin araç istekleri (yapıldığının kanıtı değildir): " + json.dumps([c.get("function", {}) for c in m["tool_calls"]], ensure_ascii=False)}])
                continue
            raw = m.get("gemini_content")
            if not foreign and isinstance(raw, dict) and isinstance(raw.get("parts"), list):
                for tc in m.get("tool_calls") or []:
                    names[tc.get("id")] = (tc.get("function") or {}).get("name", "")
                    if tc.get("gemini_call_id"):
                        native_ids[tc["id"]] = tc["gemini_call_id"]
                add("model", copy.deepcopy(raw["parts"]))
                continue
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                p = {"functionCall": {"name": fn.get("name", ""), "args": args if isinstance(args, dict) else {"value": args}}}
                if tc.get("gemini_call_id"):
                    p["functionCall"]["id"] = tc["gemini_call_id"]
                    native_ids[tc.get("id")] = tc["gemini_call_id"]
                if tc.get("thought_signature"):
                    p["thoughtSignature"] = tc["thought_signature"]
                parts.append(p)
                names[tc.get("id")] = fn.get("name", "")
            add("model", parts or [{"text": " "}])
        elif role == "tool":
            if m.get("tool_call_id") in flattened:
                add("user", [{"text": "Önceki aracın gerçek sonucu: " + str(m.get("name", "")) + "\n" + str(m.get("content", ""))}])
                continue
            name = m.get("name") or names.get(m.get("tool_call_id"), "tool")
            res = m.get("content")
            try:
                val = json.loads(res) if isinstance(res, str) and res[:1] in "{[" else res
            except Exception:
                val = res
            response = {"name": name, "response": val if isinstance(val, dict) else {"result": val}}
            if m.get("tool_call_id") in native_ids:
                response["id"] = native_ids[m["tool_call_id"]]
            add("user", [{"functionResponse": response}])
    if contents and contents[0]["role"] != "user":  # Gemini sohbetin kullanıcıyla başlamasını ister
        contents.insert(0, {"role": "user", "parts": [{"text": "(devam)"}]})
    sys_inst = {"parts": [{"text": "\n\n".join(s for s in system if s)}]} if any(system) else None
    return sys_inst, contents


def _lines(resp, content):
    """Akış satırları; okuma zaman aşımı olursa (henüz cevap gelmediyse) 504 olarak bildirir → üst katman diğer modeli dener."""
    try:
        for raw in resp:
            yield raw
    except (TimeoutError, OSError) as e:
        if content:
            return  # cevabın bir kısmı geldi: olanı kullan
        raise NativeError(504, f"Gemini zamanında cevap vermedi: {e}")


class NativeError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status, self.body = status, body


TIMEOUT = 20  # görev katmanı 10 sn (FAST) veya 20 sn (SMART) gönderir
_NO_THINK_CFG = set()  # bu ayarı kabul etmeyen modeller


def stream(key, model, messages, tools=None, temperature=0.7, timeout=20, tool_choice="auto"):
    """("text", parça) ... ("final", {"content", "tool_calls"}) üretir — llm.stream_chat ile aynı sözleşme."""
    sys_inst, contents = convert(messages, model=model)
    body = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if model.startswith("gemini-3") and model not in _NO_THINK_CFG:
        # Gemini 3 varsayılan olarak uzun 'düşünür' → yavaş. Sesli asistan için düşük düşünme: çok daha hızlı cevap
        body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "low"}
    if sys_inst:
        body["systemInstruction"] = sys_inst
    t = _tools(tools)
    if t:
        body["tools"] = t
        body["toolConfig"] = {"functionCallingConfig": {"mode": "ANY" if tool_choice == "required" else "AUTO"}}
    # Akış yerine TEK PARÇA istek: bazı bilgisayarlarda antivirüs/ağ HTTPS taramaları akışlı (SSE) cevabı tutup
    # bekletiyor ve JARVIS "İŞLENİYOR"da kalıyordu. Cevaplar zaten kısa; tek parça çok daha güvenilir.
    t0 = time.time()
    req = urllib.request.Request(f"{ROOT}/models/{model}:generateContent", data=json.dumps(body).encode("utf-8"),
                                 headers=headers(key), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        try:
            txt = e.read().decode("utf-8", "ignore")
        except Exception:
            txt = ""
        # Some Lite endpoints return only a generic INVALID_ARGUMENT when an optional
        # thinking setting is rejected. Retry at most once without that setting;
        # never remove tools, conversation history or function-call signatures.
        generic_400 = False
        if e.code == 400:
            try:
                detail = json.loads(txt).get("error") or {}
                generic_400 = (detail.get("status") == "INVALID_ARGUMENT"
                               and str(detail.get("message", "")).strip().rstrip(".").lower()
                               == "request contains an invalid argument")
            except (ValueError, TypeError, AttributeError):
                pass
        if (e.code == 400 and "thinkingConfig" in body["generationConfig"]
                and ("thinking" in txt.lower() or generic_400)):
            _NO_THINK_CFG.add(model)  # no second optional-setting retry for this model
            yield from stream(key, model, messages, tools, temperature, timeout, tool_choice)
            return
        print(f"[gemini] {model} HTTP {e.code} ({time.time() - t0:.1f} sn): {txt[:160]}")
        raise NativeError(e.code, txt)
    except (TimeoutError, OSError, ValueError) as e:
        print(f"[gemini] {model} cevap vermedi ({time.time() - t0:.1f} sn): {e}")
        raise NativeError(504, f"bağlantı/zaman aşımı: {e}")
    if data.get("error"):
        err = data["error"]
        raise NativeError(int(err.get("code") or 500), json.dumps(err, ensure_ascii=False))
    content, calls = [], []
    blocked = (data.get("promptFeedback") or {}).get("blockReason", "")
    selected_content = None
    for cand in (data.get("candidates") or [])[:1]:
        selected_content = cand.get("content")
        for p in (cand.get("content") or {}).get("parts") or []:
            if p.get("thought"):  # iç düşünce özeti: kullanıcıya gösterme
                continue
            if p.get("text"):
                content.append(p["text"])
            if p.get("functionCall"):
                fc = p["functionCall"]
                calls.append({"id": fc.get("id") or f"call_{len(calls)}_{int(time.time() * 1000)}", "type": "function",
                              "function": {"name": fc.get("name", ""), "arguments": json.dumps(fc.get("args") or {}, ensure_ascii=False)},
                              **({"gemini_call_id": fc["id"]} if fc.get("id") else {}),
                              **({"thought_signature": p["thoughtSignature"]} if p.get("thoughtSignature") else {})})
    print(f"[gemini] {model} {time.time() - t0:.1f} sn" + (f" · araç: {', '.join(c['function']['name'] for c in calls)}" if calls else ""))
    text = "".join(content)
    if blocked and not text and not calls:
        text = "Bu isteğe Google'ın güvenlik filtresi cevap vermeye izin vermedi."
    if text:
        yield ("text", text)
    yield ("final", {"content": text, "tool_calls": calls, "gemini_content": selected_content, "tool_provider": "gemini", "tool_model": model})


def embed(key, model, texts, timeout=40):
    body = {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": t}]}} for t in texts]}
    req = urllib.request.Request(f"{ROOT}/models/{model}:batchEmbedContents", data=json.dumps(body).encode(), method="POST", headers=headers(key))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return [e["values"] for e in data["embeddings"]]
