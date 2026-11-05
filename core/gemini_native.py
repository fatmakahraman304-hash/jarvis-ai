"""Gemini'ye Google'ın KENDİ uç noktasıyla bağlanır (generativelanguage.googleapis.com/v1beta, x-goog-api-key).

Neden: 2026'da AI Studio yeni anahtarları 'AQ.' ile üretiyor; bunlar OpenAI uyumlu katmanda 'Authorization: Bearer'
ile reddediliyor ("API key not valid" / ACCESS_TOKEN_TYPE_UNSUPPORTED). Kendi uç noktası hem eski 'AIza' hem yeni
'AQ.' anahtarlarla çalışır. Bu modül JARVIS'in OpenAI biçimli mesaj/araç akışını Gemini biçimine çevirir ve geri çevirir;
Gemini 3'ün araç çağrısı 'thoughtSignature' imzalarını da korur (yoksa çok adımlı araç kullanımı 400 verir).
"""
import json
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


def convert(messages):
    """OpenAI mesajları → (systemInstruction, contents)."""
    system, contents = [], []

    def add(role, parts):
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": list(parts)})

    names = {}
    for m in messages:
        role = m.get("role")
        if role == "system":
            system.append(m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"), ensure_ascii=False))
        elif role == "user":
            add("user", _user_parts(m.get("content")))
        elif role == "assistant":
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
                if tc.get("thought_signature"):
                    p["thoughtSignature"] = tc["thought_signature"]
                parts.append(p)
                names[tc.get("id")] = fn.get("name", "")
            add("model", parts or [{"text": " "}])
        elif role == "tool":
            name = m.get("name") or names.get(m.get("tool_call_id"), "tool")
            res = m.get("content")
            try:
                val = json.loads(res) if isinstance(res, str) and res[:1] in "{[" else res
            except Exception:
                val = res
            add("user", [{"functionResponse": {"name": name, "response": val if isinstance(val, dict) else {"result": val}}}])
    if contents and contents[0]["role"] != "user":  # Gemini sohbetin kullanıcıyla başlamasını ister
        contents.insert(0, {"role": "user", "parts": [{"text": "(devam)"}]})
    sys_inst = {"parts": [{"text": "\n\n".join(s for s in system if s)}]} if any(system) else None
    return sys_inst, contents


class NativeError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status, self.body = status, body


def stream(key, model, messages, tools=None, temperature=0.7, timeout=90):
    """("text", parça) ... ("final", {"content", "tool_calls"}) üretir — llm.stream_chat ile aynı sözleşme."""
    sys_inst, contents = convert(messages)
    body = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if sys_inst:
        body["systemInstruction"] = sys_inst
    t = _tools(tools)
    if t:
        body["tools"] = t
        body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
    req = urllib.request.Request(f"{ROOT}/models/{model}:streamGenerateContent?alt=sse", data=json.dumps(body).encode("utf-8"),
                                 headers=headers(key), method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        try:
            txt = e.read().decode("utf-8", "ignore")
        except Exception:
            txt = ""
        raise NativeError(e.code, txt)
    content, calls, blocked = [], [], ""
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            try:
                chunk = json.loads(line[5:].strip())
            except Exception:
                continue
            if chunk.get("error"):
                err = chunk["error"]
                raise NativeError(int(err.get("code") or 500), json.dumps(err, ensure_ascii=False))
            if (chunk.get("promptFeedback") or {}).get("blockReason"):
                blocked = chunk["promptFeedback"]["blockReason"]
            for cand in chunk.get("candidates") or []:
                for p in (cand.get("content") or {}).get("parts") or []:
                    if p.get("thought"):  # iç düşünce özeti: kullanıcıya gösterme
                        continue
                    if p.get("text"):
                        content.append(p["text"])
                        yield ("text", p["text"])
                    if p.get("functionCall"):
                        fc = p["functionCall"]
                        calls.append({"id": f"call_{len(calls)}_{int(time.time() * 1000)}", "type": "function",
                                      "function": {"name": fc.get("name", ""), "arguments": json.dumps(fc.get("args") or {}, ensure_ascii=False)},
                                      **({"thought_signature": p["thoughtSignature"]} if p.get("thoughtSignature") else {})})
    if blocked and not content and not calls:
        msg = "Bu isteğe Google'ın güvenlik filtresi cevap vermeye izin vermedi."
        yield ("text", msg)
        content.append(msg)
    yield ("final", {"content": "".join(content), "tool_calls": calls})


def embed(key, model, texts, timeout=40):
    body = {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": t}]}} for t in texts]}
    req = urllib.request.Request(f"{ROOT}/models/{model}:batchEmbedContents", data=json.dumps(body).encode(), method="POST", headers=headers(key))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return [e["values"] for e in data["embeddings"]]
