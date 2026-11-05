"""JARVIS MASTER CONTROL: çalışma modları (sessiz/araştırma/mühendislik/komuta/acil), komut makroları, modülleri açıp kapatma,
tek bakışta her şeyi gösteren komuta merkezi verisi."""
import json
import re
import threading
import time

from .. import memory
from ..config import load_settings, save_settings
from ..tools import S, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS macros(name TEXT PRIMARY KEY, trigger TEXT, steps TEXT, runs INTEGER DEFAULT 0, last_run REAL, created REAL);
""")

MODES = {
    "normal": {"ad": "Normal", "açıklama": "Varsayılan çalışma.", "ipucu": ""},
    "sessiz": {"ad": "Sessiz", "açıklama": "Sesli yanıt ve önemsiz bildirim sesi kapalı; yalnızca alarm, güvenlik ve hatalar seslendirilir.",
               "ipucu": "SESSİZ MOD: yanıtların kısa olsun, kullanıcıyı gereksiz bildirimle rahatsız etme."},
    "araştırma": {"ad": "Araştırma", "açıklama": "Derinlemesine araştırma: birden çok kaynak, kaynak gösterme, ekip ve web araçları önde.",
                  "ipucu": "ARAŞTIRMA MODU: Cevap vermeden önce web'de birden çok kaynağa bak, karşılaştır, kaynakları (link) listele; gerekirse team_task ile araştırmacı/analist ekibi kur.",
                  "gruplar": ["web", "team", "semantic", "office"]},
    "mühendislik": {"ad": "Mühendislik", "açıklama": "Tasarım atölyesi, hologram, simülasyon, kod ve robotik araçları açık; teknik ve sayısal yanıtlar.",
                    "ipucu": "MÜHENDİSLİK MODU: Teknik, ölçülü ve sayısal cevap ver; tasarımları atölyede (holo_*), hesapları sim_show/circuit_solve ile göster; kod gerekirse dosya olarak yaz.",
                    "gruplar": ["holo", "selfdev", "smarthome", "control", "daily"], "görünüm": "lab"},
    "komuta": {"ad": "Komuta", "açıklama": "Komuta merkezi açık: sistem, ekip, görevler, güvenlik, bağlantılar canlı izlenir.",
               "ipucu": "KOMUTA MODU: Durum raporlarını madde madde, kısa ve askerî netlikte ver.", "gruplar": ["control", "automation", "team"]},
    "acil": {"ad": "Acil durum", "açıklama": "Kırmızı alarm görünümü; sadece kritik bildirimler; güvenlik ve ağ sık kontrol edilir; çok kısa ve net talimatlar.",
             "ipucu": "ACİL DURUM MODU: Çok kısa, net, adım adım talimat ver. Önce güvenlik. Gerekirse kullanıcıya 112'yi aramasını söyle (sen arayamazsın).",
             "gruplar": ["control", "windows", "geo"]},
}


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").lower().replace("İ", "i").replace("I", "ı")).strip(" .!?")


def current_mode():
    m = load_settings().get("work_mode", "normal")
    return m if m in MODES else "normal"


def mode_hint():
    m = MODES[current_mode()]
    return m["ipucu"], set(m.get("gruplar", []))


def set_mode(mode):
    key = _norm(mode).replace("muhendislik", "mühendislik").replace("arastirma", "araştırma")
    key = next((k for k in MODES if key.startswith(k[:4]) or key == MODES[k]["ad"].lower()), None)
    if not key:
        return "Modlar: " + ", ".join(MODES)
    save_settings({"work_mode": key})
    memory.notify(key, "mode")  # açık arayüzler modu hemen uygular
    m = MODES[key]
    return {"ui": "mode", "mode": key, "ad": m["ad"], "açıklama": m["açıklama"], "view": m.get("görünüm", "")}


def list_modes():
    cur = current_mode()
    return [{"mod": k, "ad": v["ad"], "açıklama": v["açıklama"], "etkin": k == cur} for k, v in MODES.items()]


# ---------------- makrolar ----------------

def macro_create(name, steps, trigger=""):
    """Adımlar ';' ya da satır satır: doğal dil komutları; özel adımlar: 'mod:sessiz', 'bekle:5', 'söyle:Metin', 'makro:başka'."""
    items = steps if isinstance(steps, list) else [s.strip() for s in re.split(r"[;\n]", str(steps)) if s.strip()]
    if not items:
        return "Adım yok."
    memory._q("INSERT OR REPLACE INTO macros(name,trigger,steps,runs,created) VALUES(?,?,?,COALESCE((SELECT runs FROM macros WHERE name=?),0),?)",
              (_norm(name), _norm(trigger or name), json.dumps(items, ensure_ascii=False), _norm(name), time.time()), commit=True)
    return {"makro": _norm(name), "tetik": _norm(trigger or name), "adımlar": items}


def macro_list():
    rows = memory._q("SELECT * FROM macros ORDER BY name")
    return [{"ad": r["name"], "tetik": r["trigger"], "adımlar": json.loads(r["steps"]), "çalışma": r["runs"]} for r in rows] or "Makro yok."


def macro_delete(name):
    if not memory._q("SELECT name FROM macros WHERE name=?", (_norm(name),), one=True):
        return "Böyle bir makro yok."
    memory._q("DELETE FROM macros WHERE name=?", (_norm(name),), commit=True)
    return "Silindi."


_tls = threading.local()


def macro_run(name, persona="", _depth=0):
    r = memory._q("SELECT * FROM macros WHERE name=? OR trigger=?", (_norm(name), _norm(name)), one=True)
    if not r:
        return f"'{name}' adında makro yok."
    if _depth > 2 or getattr(_tls, "running", 0) > 2:
        return "Makrolar en fazla 3 kat iç içe çalışabilir."
    from .. import brain
    from . import control
    _tls.running = getattr(_tls, "running", 0) + 1
    log, confirms = [], []
    try:
        for step in json.loads(r["steps"]):
            if control.ESTOP.is_set():
                log.append({"adım": step, "sonuç": "ACİL DURDURMA: makro kesildi"})
                break
            low = _norm(step)
            if low.startswith(("mod:", "mode:")):
                res = set_mode(step.split(":", 1)[1])
                log.append({"adım": step, "sonuç": res["ad"] if isinstance(res, dict) else res})
            elif low.startswith(("bekle:", "wait:")):
                time.sleep(min(float(re.sub(r"[^\d.]", "", step.split(":", 1)[1]) or 1), 600))
                log.append({"adım": step, "sonuç": "beklendi"})
            elif low.startswith(("söyle:", "say:")):
                memory.notify(step.split(":", 1)[1].strip(), "info")
                log.append({"adım": step, "sonuç": "söylendi"})
            elif low.startswith("makro:"):
                log.append({"adım": step, "sonuç": macro_run(step.split(":", 1)[1], persona, _depth + 1)})
            else:
                text, conf, _ = brain.collect(brain.chat(step, persona or None, session="macro", source="web", hidden=True))
                confirms += [c["text"] for c in conf]
                log.append({"adım": step, "sonuç": (text or "")[:300]})
        memory._q("UPDATE macros SET runs=runs+1, last_run=? WHERE name=?", (time.time(), r["name"]), commit=True)
    finally:
        _tls.running -= 1
    out = {"makro": r["name"], "adımlar": log}
    if confirms:
        out["onay_bekleyen"] = confirms
    return out


def match_trigger(text):
    """Kullanıcının söylediği tam olarak bir makro tetikleyicisiyse adını döndürür."""
    t = _norm(text)
    for w in ("jarvis", "friday", "ultron"):
        t = re.sub(rf"^(hey )?{w},? ", "", t)
    r = memory._q("SELECT name FROM macros WHERE trigger=? OR name=?", (t, t), one=True)
    return r["name"] if r else None


# ---------------- modüller ----------------

def module_list():
    from ..tools import GROUP_INFO, TOOL_GROUP
    off = set(load_settings().get("disabled_groups", []))
    cnt = {}
    for g in TOOL_GROUP.values():
        cnt[g] = cnt.get(g, 0) + 1
    return [{"modül": g, "açıklama": GROUP_INFO.get(g, ("",))[0], "araç": cnt.get(g, 0), "açık": g not in off} for g in sorted(cnt)]


def module_toggle(module, on=True):
    from ..tools import TOOL_GROUP
    g = _norm(module)
    groups = set(TOOL_GROUP.values())
    if g not in groups:
        cand = [x for x in groups if x.startswith(g[:4])]
        if len(cand) != 1:
            return "Modüller: " + ", ".join(sorted(groups))
        g = cand[0]
    if g == "core":
        return "Çekirdek modül kapatılamaz."
    off = set(load_settings().get("disabled_groups", []))
    on = str(on).lower() not in ("false", "0", "kapat", "off")
    (off.discard if on else off.add)(g)
    save_settings({"disabled_groups": sorted(off)})
    return {"modül": g, "durum": "açık" if on else "kapalı", "kapalılar": sorted(off)}


def disabled_groups():
    return set(load_settings().get("disabled_groups", []))


# ---------------- komuta merkezi ----------------

def snapshot():
    from .. import llm, tools
    from . import control
    s = load_settings()
    out = {"zaman": time.time(), "mod": current_mode(), "modlar": list_modes()}
    try:
        st = tools.system_status()
        out["sistem"] = st if isinstance(st, dict) else {}
    except Exception:
        out["sistem"] = {}
    try:
        import psutil
        n = psutil.net_io_counters()
        out["sistem"]["ağ_gönderilen_mb"] = round(n.bytes_sent / 1e6)
        out["sistem"]["ağ_alınan_mb"] = round(n.bytes_recv / 1e6)
    except Exception:
        pass
    out["güvenlik"] = {"acil_durdurma": control.ESTOP.is_set(), "güvenli_mod": control.STATE.get("safe_mode"), "çevrimiçi": control.STATE.get("online"),
                       "misafir_modu": bool(s.get("guest_mode"))}
    out["modeller"] = [{"id": p, "ad": v.get("name", p), "hazır": llm.configured(p)} for p, v in llm.PROVIDERS.items()]
    try:
        from . import team
        live = []
        for rid, lv in sorted(team._runs_live.items(), reverse=True)[:4]:
            plan = {t["id"]: t for t in lv["plan"]}
            live.append({"no": rid, "hedef": lv["goal"][:90], "bitti": lv.get("bitti", False),
                         "ajanlar": [{"id": k, "rol": plan.get(k, {}).get("role", "?"), "görev": plan.get(k, {}).get("task", "")[:70], "durum": v} for k, v in lv["durum"].items()]})
        out["ekip"] = live
        out["ekip_geçmiş"] = team.team_status() if not isinstance(team.team_status(), str) else []
    except Exception:
        out["ekip"], out["ekip_geçmiş"] = [], []
    now = time.time()
    try:
        out["görevler"] = [{"no": r["id"], "görev": r["prompt"][:80], "sonraki": r["next_run"], "tür": r["kind"]}
                           for r in memory._q("SELECT * FROM tasks WHERE enabled=1 ORDER BY next_run LIMIT 6")]
    except Exception:
        out["görevler"] = []
    try:
        out["alarmlar"] = [{"saat": r["at"], "etiket": r["label"]} for r in memory._q("SELECT * FROM alarms WHERE fired=0 AND at>? ORDER BY at LIMIT 4", (now,))]
    except Exception:
        out["alarmlar"] = []
    out["hatırlatmalar"] = [{"saat": r["due"], "metin": r["text"]} for r in memory._q("SELECT * FROM reminders WHERE fired=0 ORDER BY due LIMIT 4")]
    try:
        out["yapılacaklar"] = [{"metin": r["text"], "öncelik": r["priority"]} for r in memory._q("SELECT * FROM todos WHERE done=0 ORDER BY due IS NULL, due LIMIT 5")]
    except Exception:
        out["yapılacaklar"] = []
    acts = memory.recent_actions(12)
    out["işlemler"] = [{"araç": a["tool"], "ok": bool(a["ok"]), "zaman": a["ts"], "sonuç": (a["result"] or "")[:80]} for a in acts]
    day = [a for a in memory.recent_actions(500) if now - a["ts"] < 86400]
    out["bugün"] = {"işlem": len(day), "başarılı": sum(1 for a in day if a["ok"]), "mesaj": (memory._q("SELECT COUNT(*) n FROM messages WHERE ts>?", (now - 86400,), one=True) or {"n": 0})["n"]}
    out["bildirimler"] = [{"metin": n["text"][:120], "tür": n["kind"], "zaman": n["ts"]} for n in memory._q("SELECT * FROM notifications ORDER BY id DESC LIMIT 6")]
    out["bağlantılar"] = _connections(s)
    try:
        out["bilgisayarlar"] = [{"ad": r["name"], "adres": r["url"], "çevrimiçi": bool(r["last_seen"] and now - r["last_seen"] < 150),
                                 "durum": (json.loads(r["info"] or "{}").get("durum") or {})} for r in memory._q("SELECT * FROM nodes ORDER BY name")]
        out["kuyruk"] = (memory._q("SELECT COUNT(*) n FROM node_queue WHERE status='bekliyor'", one=True) or {"n": 0})["n"]
    except Exception:
        out["bilgisayarlar"], out["kuyruk"] = [], 0
    out["modüller"] = module_list()
    ml = macro_list()
    out["makrolar"] = ml if isinstance(ml, list) else []
    try:
        out["kurulum"] = readiness_cached()
    except Exception:
        out["kurulum"] = None
    return out


_ready_cache = {"t": 0, "v": None}


def readiness_cached():
    if time.time() - _ready_cache["t"] > 60:
        _ready_cache.update({"t": time.time(), "v": readiness()})
    return _ready_cache["v"]


def _connections(s):
    from ..config import env
    from ..config import DATA
    c = {"Google": (DATA / "google_token.json").exists(), "Telegram": bool(env("TELEGRAM_BOT_TOKEN")), "Home Assistant": bool(env("HA_URL") and env("HA_TOKEN")),
         "Robot": bool(s.get("robot_port") or s.get("robot_url")), "Groq (ses)": bool(env("GROQ_API_KEY")), "Uydu yangın (FIRMS)": bool(env("FIRMS_MAP_KEY")),
         "Canlı gemi (AIS)": bool(env("AISSTREAM_KEY"))}
    try:
        rows = memory._q("SELECT last_seen FROM nodes")
        c["Diğer JARVIS'ler"] = sum(1 for r in rows if r["last_seen"] and time.time() - r["last_seen"] < 150)
    except Exception:
        pass
    return c


# ---------------- kurulum durumu ----------------

PKGS = [  # (modül, pip adı, neyi açar, zorunlu mu)
    ("starlette", "starlette", "web sunucusu", True), ("uvicorn", "uvicorn", "web sunucusu", True), ("psutil", "psutil", "sistem durumu", True),
    ("edge_tts", "edge-tts", "film tadında sinir ağı sesleri", False), ("PIL", "pillow", "ekranı görme, fotoğraf düzenleme, logo", False),
    ("pypdf", "pypdf", "PDF okuma/birleştirme, kütüphane", False), ("docx", "python-docx", "Word", False), ("openpyxl", "openpyxl", "Excel", False),
    ("pptx", "python-pptx", "PowerPoint", False), ("reportlab", "reportlab", "PDF/fatura üretme", False), ("matplotlib", "matplotlib", "grafikler", False),
    ("send2trash", "send2trash", "silinenler geri dönüşüm kutusuna", False), ("numpy", "numpy", "ses kimliği", False), ("cryptography", "cryptography", "kasa, https", False),
    ("playwright", "playwright", "tarayıcı otomasyonu", False), ("serial", "pyserial", "Arduino/robot", False), ("cv2", "opencv-python", "sunucu kamerası", False),
    ("youtube_transcript_api", "youtube-transcript-api", "YouTube özeti", False),
]


def readiness():
    """Neyin hazır, neyin eksik olduğunu ve nasıl tamamlanacağını listeler."""
    import importlib.util
    import shutil
    import sys
    from .. import llm
    from ..config import env
    out = []
    ok_py = sys.version_info >= (3, 10)
    out.append({"bileşen": f"Python {sys.version.split()[0]}", "durum": ok_py, "açar": "her şey", "çözüm": "" if ok_py else "Python 3.10+ kur"})
    for mod, pipn, what, req in PKGS:
        ok = importlib.util.find_spec(mod) is not None
        out.append({"bileşen": pipn, "durum": ok, "açar": what, "zorunlu": req, "çözüm": "" if ok else f"pip install {pipn}"})
    models = [p for p in llm.PROVIDERS if llm.configured(p)]
    out.append({"bileşen": "Yapay zekâ modeli", "durum": bool(models), "açar": "beyin", "zorunlu": True, "ayrıntı": ", ".join(models),
                "çözüm": "" if models else "Ayarlar > Modeller: en az bir ücretsiz anahtar (Gemini/Groq)"})
    out.append({"bileşen": "Groq anahtarı", "durum": bool(env("GROQ_API_KEY")), "açar": "ses dosyası/Telegram sesli mesaj yazıya çevirme, tercüman, altyazı",
                "çözüm": "" if env("GROQ_API_KEY") else "console.groq.com/keys → Ayarlar > Modeller"})
    ff = bool(shutil.which("ffmpeg"))
    if not ff:
        try:
            from .studio import _ff
            ff = bool(_ff())
        except Exception:
            ff = False
    out.append({"bileşen": "ffmpeg", "durum": ff, "açar": "video düzenleme/analiz, montaj, GIF", "çözüm": "" if ff else "winget install Gyan.FFmpeg (ya da 'ffmpeg kur' de)"})
    out.append({"bileşen": "NVIDIA ekran kartı aracı", "durum": bool(shutil.which("nvidia-smi")), "açar": "GPU kullanımı/sıcaklığı", "çözüm": "NVIDIA sürücüsüyle gelir (AMD/Intel'de GPU verisi sınırlı)"})
    for name, keys, what, how in (("Google (Gmail/Takvim)", ["GOOGLE_CLIENT_ID"], "e-posta ve takvim", "Ayarlar > Bağlantılar'daki adımlar"),
                                  ("Telegram botu", ["TELEGRAM_BOT_TOKEN"], "her yerden erişim", "@BotFather → .env TELEGRAM_BOT_TOKEN"),
                                  ("Home Assistant", ["HA_URL", "HA_TOKEN"], "akıllı ev + ev ikizi", ".env HA_URL ve HA_TOKEN"),
                                  ("NASA FIRMS", ["FIRMS_MAP_KEY"], "uydudan yangınlar", "firms.modaps.eosdis.nasa.gov/api/map_key"),
                                  ("AIS gemi", ["AISSTREAM_KEY"], "canlı gemiler", "aisstream.io"),
                                  ("OBS", ["OBS_PASSWORD"], "yayın/kayıt kontrolü", "OBS > WebSocket Sunucu Ayarları")):
        ok = all(env(k) for k in keys)
        out.append({"bileşen": name, "durum": ok, "açar": what, "isteğe_bağlı": True, "çözüm": "" if ok else how})
    eksik_zorunlu = [x["bileşen"] for x in out if not x["durum"] and x.get("zorunlu")]
    return {"hazır": not eksik_zorunlu, "eksik_zorunlu": eksik_zorunlu, "bileşenler": out}


def command_center(open=True):
    return {"ui": "command", "open": str(open).lower() not in ("false", "0")}


TOOLS = {
    "set_mode": (set_mode, _schema("Çalışma modunu değiştirir: normal, sessiz, araştırma, mühendislik, komuta, acil.", {"mode": S("mod")}, ["mode"]), False),
    "list_modes": (list_modes, _schema("Çalışma modlarını listeler.", {}), False),
    "macro_create": (macro_create, _schema("Tek komutla birden çok işlem yapan makro oluşturur (ör. 'film modu': ışıkları kıs; Netflix aç; sessiz mod).",
                                           {"name": S("makro adı"), "steps": S("adımlar ; ile. Özel: mod:sessiz, bekle:5, söyle:metin, makro:ad"), "trigger": S("tetikleyici cümle (boş: ad)")},
                                           ["name", "steps"]), False),
    "macro_run": (macro_run, _schema("Makroyu çalıştırır.", {"name": S("makro adı")}, ["name"]), False),
    "macro_list": (macro_list, _schema("Makroları listeler.", {}), False),
    "macro_delete": (macro_delete, _schema("Makroyu siler.", {"name": S("ad")}, ["name"]), True),
    "module_list": (module_list, _schema("JARVIS modüllerini (yetenek gruplarını) ve açık/kapalı durumlarını listeler.", {}), False),
    "module_toggle": (module_toggle, _schema("Bir modülü açar/kapatır (kapalı modülün araçları kullanılmaz).", {"module": S("modül"), "on": {"type": "boolean"}}, ["module"]), False),
    "readiness_check": (lambda: readiness(), _schema("Kurulum durumu: hangi bileşenler hazır, hangileri eksik ve nasıl tamamlanır.", {}), False),
    "command_center": (command_center, _schema("JARVIS MASTER CONTROL komuta merkezini ekranda açar/kapatır.", {"open": {"type": "boolean"}}), False),
}
