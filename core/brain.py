"""TEK BEYİN: her platform (web, telefon, Telegram) aynı fonksiyonu çağırır.

chat() bir olay akışı üretir:
  {"type":"provider", provider, model}   hangi model cevaplıyor
  {"type":"token", text}                 cevap parçası
  {"type":"tool", name, args, result}    çalışan araç
  {"type":"confirm", id, name, args}     onay bekleyen kritik işlem
  {"type":"done", text, provider, model}
  {"type":"error", text}
"""
import json
import secrets
import threading
import time

from . import llm, memory, personas, tools
from .config import load_settings

MAX_STEPS = 8
TURN_BUDGET = 100  # bir cevap için en fazla bu kadar saniye araç/model döngüsü; sonra eldekiyle cevap verilir
_pending = {}
_plock = threading.Lock()

NO_PROVIDER_MSG = (
    "Henüz hiçbir yapay zekâ modeli bağlı değil. Ayarlar panelinden veya .env dosyasından "
    "en az bir ücretsiz anahtar ekleyin: GEMINI_API_KEY (aistudio.google.com), "
    "GROQ_API_KEY (console.groq.com) ya da OPENROUTER_API_KEY (openrouter.ai). "
    "İnternetsiz çalışmak için Ollama kurabilirsiniz."
)

# Mark-LVI-inspired low-latency conversation layer.
MAX_HISTORY_CHARS = 24_000  # rolling prompt window; SQLite keeps the full archive

_TURKISH_MARKERS = {
    "bana", "benim", "lütfen", "lutfen", "nedir", "nasil", "nasıl",
    "nerede", "bugun", "bugün", "yarin", "yarın", "dosya", "dosyaları",
    "bilgisayar", "ekran", "arastir", "araştır", "goster", "göster",
    "hazirla", "hazırla", "oku", "yaz", "sil", "kur", "ac", "aç",
    "kapat", "olustur", "oluştur", "cevir", "çevir", "hatirla",
    "hatırla", "saat", "hava", "durumu", "ozetle", "özetle",
    "kontrol", "indir", "gonder", "gönder", "guncelle", "güncelle",
    "bul", "dosyayi", "dosyayı", "ben", "şunu", "sunu", "bunu",
}


def _history_window(rows, max_chars=MAX_HISTORY_CHARS):
    """Keep the newest conversation context within a predictable prompt budget.

    The full transcript remains in SQLite. Only the model request is compacted,
    newest-first, so long old replies cannot slow every later turn.
    """
    budget = max(1, int(max_chars))
    kept = []
    used = 0
    for item in reversed(rows or []):
        role = item.get("role")
        content = str(item.get("content") or "")
        if role not in ("user", "assistant") or not content:
            continue
        room = budget - used
        if len(content) > room:
            if not kept and room > 0:
                kept.append({"role": role, "content": content[-room:]})
            break
        kept.append({"role": role, "content": content})
        used += len(content)
    kept.reverse()
    return kept


def _quick_ack(text, groups):
    """Return a short local acknowledgement for work that needs a tool group.

    No extra model request is made: this is emitted before the first provider
    round-trip, while the real streamed answer is being generated.
    """
    active = set(groups or ()) - {"core", "plugins", "semantic"}
    if not active:
        return ""

    tokens = set(re.findall(r"[^\\W\\d_]+", (text or "").casefold(), flags=re.UNICODE))
    is_turkish = (
        any(ch in (text or "") for ch in "çğıöşüÇĞİÖŞÜ")
        or bool(tokens & _TURKISH_MARKERS)
    )

    research = active & {"browser", "geo", "space", "worldwatch", "translate", "internet", "knowledge"}
    computer = active & {"computer", "windows", "control", "cams", "screens"}
    prepare = active & {"office", "team", "studio", "automation", "life", "daily"}

    if is_turkish:
        if research:
            return "Hemen araştırıyorum, efendim."
        if computer:
            return "Bilgisayarı kontrol ediyorum, efendim."
        if prepare:
            return "Hemen hazırlıyorum, efendim."
        return "Hemen ilgileniyorum, efendim."
    if research:
        return "I'm looking into that now."
    if computer:
        return "I'm checking your system now."
    if prepare:
        return "I'll prepare that now."
    return "On it. I'll take care of that."



def _system_prompt(persona, source):
    facts = memory.facts(60)
    fact_txt = "\n".join(f"- {f['fact']}" for f in facts) or "- (henüz kayıtlı bilgi yok)"
    platform_note = {
        "telegram": "Kullanıcı Telegram'dan yazıyor (uzaktan).",
        "phone": "Kullanıcı telefondan bağlanıyor.",
        "remote": "Komut, ağdaki başka bir JARVIS bilgisayarından (kullanıcının kendi bilgisayarı) geldi; sonucu kısa raporla.",
        "auto": "Bu, zamanlanmış OTOMATİK bir görev; kullanıcı başında değil. Soru sorma, en makul şekilde yap ve rapor ver.",
    }.get(source, "Kullanıcı bilgisayarın başında, arayüzden konuşuyor.")
    lessons = ""
    try:
        fails = [a for a in memory.recent_actions(40) if not a["ok"] and time.time() - a["ts"] < 86400][:5]
        if fails:
            lessons = "SON HATALARINDAN DERS (aynı hatayı tekrarlama, farklı yol dene):\n" + "\n".join(
                f"- {a['tool']}({a['args'][:80]}) → {a['result'][:120]}" for a in fails) + "\n"
    except Exception:
        pass
    return (
        f"{persona['prompt']}\n{personas.COMMON_RULES}\n{lessons}"
        f"Şu an: {tools.get_time()}. {platform_note}\n"
        f"Araç grupların konuya göre açılır; gereken araç elinde yoksa enable_tools ile aç.\n"
        f"KULLANICI HAKKINDA BİLDİKLERİN:\n{fact_txt}"
    )


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _new_pending(name, args, persona_id, session, source):
    pid = secrets.token_hex(3)
    with _plock:
        _pending[pid] = {"id": pid, "name": name, "args": args, "persona": persona_id,
                         "session": session, "source": source, "ts": time.time()}
    return pid


def pending_list():
    with _plock:
        return list(_pending.values())


def describe(name, args):
    return f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())})"


GUEST_BLOCKED = {"google", "vault", "habits", "selfdev", "automation", "control", "windows", "voiceid", "semantic"}


def _estop():
    try:
        from .skills.control import ESTOP
        return ESTOP.is_set()
    except Exception:
        return False


def chat(text, persona_id=None, session="main", source="web", hidden=False, guest=None, groups_override=None, extra_system=""):
    settings = load_settings()
    if guest is None:
        guest = bool(settings.get("guest_mode"))
    persona_id = (persona_id or settings.get("persona") or "jarvis").lower()
    persona = personas.get(persona_id)
    pconf = settings["personas"].get(persona["id"], {})

    hist = memory.history(session, 20)
    if not hidden:
        memory.add_message(session, "user", text, persona["id"], source)

    mode_tip, mode_groups, off_groups = "", set(), set()
    try:
        from .skills import command as _cmd
        mode_tip, mode_groups = _cmd.mode_hint()
        off_groups = _cmd.disabled_groups()
        mac = None if (hidden or guest) else _cmd.match_trigger(text)
        if mac:  # söylenen cümle bir makro tetikleyicisi: doğrudan çalıştır
            yield {"type": "tool", "name": "macro_run", "args": {"name": mac}, "status": "running"}
            res = _cmd.macro_run(mac, persona["id"])
            yield {"type": "tool", "name": "macro_run", "args": {"name": mac}, "status": "done", "result": json.dumps(res, ensure_ascii=False, default=str)[:600]}
            steps = res.get("adımlar", []) if isinstance(res, dict) else []
            msg = f"'{mac}' makrosu çalıştı: {len(steps)} adım." + (f" Onay bekleyen: {len(res['onay_bekleyen'])}." if isinstance(res, dict) and res.get("onay_bekleyen") else "") if steps else str(res)
            memory.add_message(session, "assistant", msg, persona["id"], source)
            yield {"type": "token", "text": msg}
            yield {"type": "done", "text": msg, "provider": "makro", "model": ""}
            return
    except Exception:
        pass

    sp = _system_prompt(persona, source) if not guest else (
        f"{persona['prompt']}\n{personas.COMMON_RULES}\nMİSAFİR MODU: Konuşan kişi sahibi değil. Kişisel bilgi, e-posta, dosya, "
        f"şifre ve hafıza paylaşma; kritik işlem yapma. Genel sorulara nazikçe cevap ver. Şu an: {tools.get_time()}.")
    if mode_tip:
        sp = sp + "\n" + mode_tip
    if extra_system:
        sp = extra_system + "\n\n" + sp
    messages = [{"role": "system", "content": sp}]
    for h in _history_window(hist):
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": text})

    full_text = ""
    used = {"provider": "", "model": ""}
    context = text + " " + " ".join(h["content"] for h in hist[-2:] if h["role"] == "user")
    groups = set(groups_override) | {"core"} if groups_override else tools.pick_groups(context)
    if not groups_override:
        groups |= mode_groups
    groups -= off_groups - {"core"}
    if guest:
        groups -= GUEST_BLOCKED

    # Speak immediately while the web/phone model request is starting.
    if not hidden and source in ("web", "phone"):
        ack = _quick_ack(text, groups)
        if ack:
            yield {"type": "ack", "text": ack}

    turn_t0 = time.time()
    seen_calls = {}
    for _step in range(MAX_STEPS):
        if time.time() - turn_t0 > TURN_BUDGET:
            print(f"[beyin] {TURN_BUDGET} sn doldu, eldeki bilgiyle cevaplanıyor")
            break
        if _estop() and source == "auto":
            yield {"type": "error", "text": "Acil durdurma etkin: otomatik işlem yapılmadı."}
            break
        final = None
        step_text = ""
        for ev in llm.route(pconf.get("providers", []), messages, tools.specs(groups), pconf.get("model", "")):
            kind, data = ev
            if kind == "provider":
                used = {"provider": data["provider"], "model": data["model"]}
                yield {"type": "provider", **data}
            elif kind == "text":
                step_text += data
                yield {"type": "token", "text": data}
            elif kind == "final":
                final = data
            elif kind == "error":
                msg = NO_PROVIDER_MSG if data == "NO_PROVIDER" else data
                yield {"type": "error", "text": msg}
                yield {"type": "done", "text": msg, **used}
                return
        if final is None:
            break
        full_text += step_text
        calls = final.get("tool_calls") or []
        if not calls:
            break
        messages.append({"role": "assistant", "content": final.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            args = _parse_args(call["function"].get("arguments"))
            if name == "enable_tools":
                req = {g.strip() for g in str(args.get("groups", "")).split(",") if g.strip() in tools.GROUP_INFO}
                groups |= req
                result = f"Açıldı: {', '.join(sorted(req)) or 'yok'}. Şimdi bu araçları kullanabilirsin."
            elif name not in tools.TOOLS:
                result = f"Bilinmeyen araç: {name}"
            elif guest and (tools.is_critical(name, args) or tools.TOOL_GROUP.get(name) in GUEST_BLOCKED):
                result = "Misafir modunda bu işleme izin yok."
            elif tools.is_critical(name, args):
                pid = _new_pending(name, args, persona["id"], session, source)
                yield {"type": "confirm", "id": pid, "name": name, "args": args, "text": describe(name, args)}
                result = (f"BU İŞLEM KULLANICI ONAYI BEKLİYOR (onay kodu {pid}). Henüz yapılmadı. "
                          "Kullanıcıya kısaca onay vermesi gerektiğini söyle.")
            elif (name, json.dumps(args, sort_keys=True, ensure_ascii=False)) in seen_calls:
                # aynı aracı aynı parametrelerle tekrar çağırma döngüsünü kır
                result = seen_calls[(name, json.dumps(args, sort_keys=True, ensure_ascii=False))] + \
                    "\n(NOT: Bu aracı az önce aynı şekilde çağırdın; sonuç yukarıda. Tekrar çağırma, şimdi cevap ver.)"
            else:
                yield {"type": "tool", "name": name, "args": args, "status": "running"}
                t1 = time.time()
                result = tools.execute(name, args)
                print(f"[araç] {name} {time.time() - t1:.1f} sn")
                seen_calls[(name, json.dumps(args, sort_keys=True, ensure_ascii=False))] = result[:4000]
                yield {"type": "tool", "name": name, "args": args, "status": "done",
                       "result": result[:30000] if (result.startswith('{') and '"ui": "' in result[:30000]) else result[:600]}
            messages.append({"role": "tool", "tool_call_id": call["id"], "name": name, "content": result})
        if full_text and not full_text.endswith((" ", "\n")):
            full_text += " "
            yield {"type": "token", "text": " "}

    full_text = full_text.strip()
    if not full_text and len(messages) > 2:
        # araçlar çalıştı ama model cevap yazmadı (ya da adım sınırı doldu): araçsız son bir çağrıyla mutlaka cevap ver
        messages.append({"role": "user", "content": "Yukarıdaki araç sonuçlarına dayanarak kullanıcıya ŞİMDİ kısa ve net cevap ver. Yeni araç çağırma."})
        for kind, data in llm.route(pconf.get("providers", []), messages, None, pconf.get("model", "")):
            if kind == "text":
                full_text += data
                yield {"type": "token", "text": data}
            elif kind == "error":
                break
        full_text = full_text.strip()
    if not full_text:
        full_text = "Bu soruya şu an cevap üretemedim; lütfen biraz farklı sorar mısın?"
        yield {"type": "token", "text": full_text}
    memory.add_message(session, "assistant", full_text, persona["id"], source, used.get("provider", ""))
    yield {"type": "done", "text": full_text, **used}


def resolve(pending_id, approve=True):
    """Onay ver / reddet; sonra beyin sonucu kullanıcıya anlatır."""
    with _plock:
        item = _pending.pop(pending_id, None)
    if not item:
        yield {"type": "error", "text": "Bu onay kodu bulunamadı veya süresi geçti."}
        yield {"type": "done", "text": ""}
        return
    if approve:
        yield {"type": "tool", "name": item["name"], "args": item["args"], "status": "running"}
        result = tools.execute(item["name"], item["args"])
        yield {"type": "tool", "name": item["name"], "args": item["args"], "status": "done", "result": result[:600]}
        note = (f"[SİSTEM NOTU] Kullanıcı {describe(item['name'], item['args'])} işlemini ONAYLADI ve işlem "
                f"çalıştırıldı. Sonuç: {result[:1500]}\nKullanıcıya sonucu kısaca bildir.")
    else:
        memory.log_action(item["name"], item["args"], "kullanıcı reddetti", False)
        note = f"[SİSTEM NOTU] Kullanıcı {describe(item['name'], item['args'])} işlemini REDDETTİ. Kısaca tamam de."
    yield from chat(note, item["persona"], item["session"], item["source"], hidden=True)


def ask(prompt, system="", persona_id=None, light=True):
    """Araçsız tek seferlik model çağrısı (planlama, değerlendirme). Metin döner.
    light=True: ücretsiz kotası geniş hafif model (sohbetin güçlü modelinin günlük hakkı korunur)."""
    settings = load_settings()
    persona = personas.get(persona_id or settings.get("persona"))
    order = settings["personas"].get(persona["id"], {}).get("providers", [])
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    out = ""
    for kind, data in llm.route(order, msgs, None, light=light):
        if kind == "text":
            out += data
        elif kind == "error":
            raise RuntimeError(NO_PROVIDER_MSG if data == "NO_PROVIDER" else data)
    return out.strip()


def collect(gen):
    """Akışı tek metne çevirir (Telegram vb. için)."""
    text, confirms, meta = "", [], {}
    for ev in gen:
        if ev["type"] == "done":
            text = ev.get("text") or text
            meta = ev
        elif ev["type"] == "confirm":
            confirms.append(ev)
        elif ev["type"] == "error" and not text:
            text = ev["text"]
    return text, confirms, meta
