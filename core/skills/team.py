"""Çoklu yapay zekâ ekibi: ana JARVIS yönetici planlar, uzman ajanlar (kendi araçları ve kendi hafızalarıyla) bağımlılık sırasına göre
paralel çalışır, sonuçlarını birbirine devreder; denetçi ajan kontrol eder, yetersiz iş geri bildirimle yeniden yaptırılır, yönetici birleşik rapor yazar."""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .. import memory
from ..tools import S, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS team_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, note TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS team_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, plan TEXT, status TEXT, results TEXT, report TEXT, created REAL, finished REAL);
CREATE TABLE IF NOT EXISTS team_stats(role TEXT, ok INTEGER, seconds REAL, retried INTEGER, ts REAL);
""")

ROLES = {
    "araştırmacı": ("İnternette araştırma yapan, kaynakları karşılaştırıp doğrulayan uzman. Her iddiaya kaynak (link) ekle.", ["worldwatch", "geo", "daily"]),
    "kodcu": ("Yazılım mühendisi. Çalışan, test edilmiş kod yazar; create_project ve run_project ile projeyi kurup testleri çalıştırır.", ["daily", "selfdev", "office"]),
    "güvenlik": ("Siber güvenlik uzmanı. Bilgisayarın güvenlik durumunu, şüpheli işlemleri, ağ ve gizlilik ayarlarını inceler; risk ve çözüm önerir.", ["windows", "control"]),
    "görüntü": ("Görüntü analisti. Ekranı, kamerayı ve görsel dosyaları inceler, ne gördüğünü kesin ve ölçülü raporlar.", ["computer"]),
    "ses": ("Ses uzmanı. Ses ve video dosyalarını yazıya çevirir, özetler, altyazı ve medya işlerini yapar.", ["media"]),
    "tasarımcı": ("3D tasarım ve mühendislik uzmanı. Hologram atölyesinde holo_scene ile ölçülü, parçalı modeller kurar; malzeme ve üretim önerir.", ["holo"]),
    "robotik": ("Robotik ve gömülü sistem uzmanı. Arduino/ESP32 kodu, sensör ve motor kontrolü, akıllı ev entegrasyonu yapar.", ["control", "smarthome", "daily"]),
    "analist": ("Veri ve finans analisti. Tablo, grafik ve rapor üretir; sayıları hesaplayarak kontrol eder.", ["office", "finance", "geo"]),
    "yazar": ("Rapor ve belge yazarı. Net, düzenli Türkçe metin ve Word/PDF/sunum hazırlar.", ["office", "google"]),
}
_runs_live = {}
_lock = threading.Lock()
_tls = threading.local()


def _role_notes(role, n=8):
    rows = memory._q("SELECT note FROM team_memory WHERE role=? ORDER BY id DESC LIMIT ?", (role, n))
    return "\n".join(f"- {r['note']}" for r in rows)


def _json_from(text):
    m = re.search(r"\[.*\]|\{.*\}", text, re.S)
    if not m:
        raise ValueError("JSON yok")
    return json.loads(m.group(0))


def make_plan(goal, roles=""):
    from .. import brain
    allowed = [r.strip() for r in roles.split(",") if r.strip() in ROLES] if roles else list(ROLES)
    prompt = (f"HEDEF: {goal}\n\nKullanılabilir uzmanlar: " + "; ".join(f"{r} ({ROLES[r][0][:60]})" for r in allowed) +
              "\n\nBu hedefi 2–6 alt göreve böl. Her görevi en uygun uzmana ver. Bir görev başka görevin sonucuna ihtiyaç duyuyorsa "
              "depends_on ile belirt. SADECE şu biçimde JSON yaz:\n"
              '[{"id":1,"role":"araştırmacı","task":"...","depends_on":[]},{"id":2,"role":"yazar","task":"...","depends_on":[1]}]')
    plan = _json_from(brain.ask(prompt, "Sen JARVIS ekip yöneticisisin. Görevleri net, ölçülebilir ve kendi başına yapılabilir yaz."))
    clean, ids = [], set()
    for t in plan[:8]:
        role = t.get("role") if t.get("role") in ROLES else "araştırmacı"
        tid = int(t.get("id", len(clean) + 1))
        clean.append({"id": tid, "role": role, "task": str(t.get("task", ""))[:800], "depends_on": [int(d) for d in t.get("depends_on", []) if int(d) != tid]})
        ids.add(tid)
    for t in clean:  # olmayan bağımlılıkları ve döngüleri temizle
        t["depends_on"] = [d for d in t["depends_on"] if d in ids and d < t["id"]]
    return clean


def _run_agent(run_id, t, inputs, feedback=""):
    prev = getattr(_tls, "inside", False)
    _tls.inside = True
    try:
        return _run_agent_inner(run_id, t, inputs, feedback)
    finally:
        _tls.inside = prev


def _run_agent_inner(run_id, t, inputs, feedback=""):
    from .. import brain
    role = t["role"]
    desc, groups = ROLES[role]
    notes = _role_notes(role)
    sys = (f"SEN JARVIS EKİBİNDE '{role.upper()}' UZMANISIN. {desc}\n"
           f"{('ÖNCEKİ İŞLERİNDEN ÖĞRENDİKLERİN:' + chr(10) + notes) if notes else ''}\n"
           "Sadece sana verilen alt görevi yap, sonunda başlıklı kısa ve kesin bir rapor yaz. Kullanıcıya soru sorma.")
    ctx = "".join(f"\n\n[#{d} numaralı görevin sonucu — {r['role']}]:\n{r['sonuç'][:2500]}" for d, r in inputs.items())
    prompt = f"ALT GÖREV #{t['id']}: {t['task']}{ctx}" + (f"\n\nDENETÇİ GERİ BİLDİRİMİ (bunu düzelt): {feedback}" if feedback else "")
    t0 = time.time()
    text, confirms, meta = brain.collect(brain.chat(prompt, None, session=f"team{run_id}_{t['id']}", source="auto", hidden=True,
                                                    groups_override=groups, extra_system=sys))
    return {"id": t["id"], "role": role, "görev": t["task"], "sonuç": text, "model": meta.get("model", ""),
            "süre_sn": round(time.time() - t0, 1), "onay_bekleyen": [c["text"] for c in confirms]}


def _review(goal, results):
    from .. import brain
    body = "\n\n".join(f"#{r['id']} ({r['role']}) {r['görev']}\nSONUÇ: {r['sonuç'][:1800]}" for r in results)
    txt = brain.ask(f"HEDEF: {goal}\n\nEKİP SONUÇLARI:\n{body}\n\nHer sonucu değerlendir. Eksik, hatalı, kaynaksız veya görevi karşılamayan olanları bul. "
                    'SADECE JSON yaz: {"sorunlu":[{"id":2,"neden":"..."}],"genel":"kısa değerlendirme"}  (sorun yoksa sorunlu boş liste)',
                    "Sen titiz bir denetçisin. Sadece gerçekten yetersiz işleri işaretle.")
    try:
        return _json_from(txt)
    except Exception:
        return {"sorunlu": [], "genel": txt[:300]}


def run_team(goal, plan, run_id=None, notify=None):
    if run_id is None:
        run_id = memory._q("INSERT INTO team_runs(goal,plan,status,created) VALUES(?,?,?,?)", (goal, json.dumps(plan, ensure_ascii=False), "çalışıyor", time.time()), commit=True)
    live = _runs_live.setdefault(run_id, {"goal": goal, "plan": plan, "durum": {t["id"]: "bekliyor" for t in plan}, "sonuç": {}})
    done = {}
    pending = {t["id"]: t for t in plan}
    with ThreadPoolExecutor(max_workers=4) as ex:
        while pending:
            ready = [t for t in pending.values() if all(d in done for d in t["depends_on"])]
            if not ready:  # çözülemeyen bağımlılık: kalanları sırayla çalıştır
                ready = list(pending.values())[:1]
            for t in ready:
                live["durum"][t["id"]] = "çalışıyor"
            futs = {ex.submit(_run_agent, run_id, t, {d: done[d] for d in t["depends_on"] if d in done}): t for t in ready}
            for f, t in futs.items():
                try:
                    r = f.result()
                except Exception as e:
                    r = {"id": t["id"], "role": t["role"], "görev": t["task"], "sonuç": f"HATA: {e}", "süre_sn": 0, "onay_bekleyen": []}
                done[t["id"]] = r
                live["durum"][t["id"]] = "bitti"
                live["sonuç"][t["id"]] = r["sonuç"][:400]
                pending.pop(t["id"], None)
    results = [done[t["id"]] for t in plan]
    # denetim + yeniden görevlendirme (en fazla bir tur)
    review = _review(goal, results)
    retried = set()
    for s in review.get("sorunlu", [])[:3]:
        tid = int(s.get("id", 0))
        t = next((x for x in plan if x["id"] == tid), None)
        if not t:
            continue
        live["durum"][tid] = "yeniden yapılıyor"
        r = _run_agent(run_id, t, {d: done[d] for d in t["depends_on"] if d in done}, s.get("neden", ""))
        r["yeniden"] = True
        done[tid] = r
        retried.add(tid)
        live["durum"][tid] = "bitti"
    results = [done[t["id"]] for t in plan]
    # performans + rol hafızası
    for r in results:
        ok = not r["sonuç"].startswith(("HATA", "Tüm modeller", "Henüz hiçbir"))
        memory._q("INSERT INTO team_stats(role,ok,seconds,retried,ts) VALUES(?,?,?,?,?)", (r["role"], int(ok), r["süre_sn"], int(r["id"] in retried), time.time()), commit=True)
        if ok:
            memory._q("INSERT INTO team_memory(role,note,ts) VALUES(?,?,?)", (r["role"], f"{time.strftime('%d.%m')} '{r['görev'][:80]}' görevini yaptım" + (" (denetçi düzeltme istedi)" if r["id"] in retried else ""), time.time()), commit=True)
    # yönetici raporu
    from .. import brain
    try:
        report = brain.ask(f"HEDEF: {goal}\n\nEKİP SONUÇLARI:\n" + "\n\n".join(f"#{r['id']} {r['role']}: {r['sonuç'][:2000]}" for r in results) +
                           f"\n\nDENETÇİ: {review.get('genel', '')}\n\nKullanıcı için birleşik, kısa ve net bir sonuç raporu yaz (başlıklarla). Bekleyen onaylar varsa belirt.",
                           "Sen JARVIS'sin, ekibin yöneticisisin.")
    except Exception as e:
        report = f"Rapor yazılamadı: {e}"
    memory._q("UPDATE team_runs SET status=?, results=?, report=?, finished=? WHERE id=?",
              ("bitti", json.dumps(results, ensure_ascii=False), report, time.time(), run_id), commit=True)
    live["bitti"] = True
    if notify:
        notify(f"Ekip görevi #{run_id} tamamlandı: {goal[:80]}", "task")
    return {"run": run_id, "rapor": report, "denetçi": review.get("genel", ""), "yeniden_yapılan": sorted(retried),
            "ajanlar": [{"id": r["id"], "rol": r["role"], "süre_sn": r["süre_sn"], "onay_bekleyen": r["onay_bekleyen"]} for r in results]}


# ===================== araçlar =====================
def team_task(goal, roles="", approve_plan=False):
    if getattr(_tls, "inside", False):
        return "Ekip üyeleri yeni ekip kuramaz."
    plan = make_plan(goal, roles)
    if str(approve_plan).lower() in ("true", "1"):
        rid = memory._q("INSERT INTO team_runs(goal,plan,status,created) VALUES(?,?,?,?)", (goal, json.dumps(plan, ensure_ascii=False), "onay bekliyor", time.time()), commit=True)
        return {"plan_no": rid, "plan": plan, "not": "Kullanıcı onaylarsa team_run(plan_no) çağır; değiştirmek isterse team_task'ı yeniden çağır."}
    return run_team(goal, plan)


def team_run(plan_no):
    r = memory._q("SELECT * FROM team_runs WHERE id=?", (int(plan_no),), one=True)
    if not r:
        return "Plan bulunamadı."
    memory._q("UPDATE team_runs SET status='çalışıyor' WHERE id=?", (r["id"],), commit=True)
    return run_team(r["goal"], json.loads(r["plan"]), r["id"])


def team_status(run_no=0):
    if run_no and int(run_no) in _runs_live:
        lv = _runs_live[int(run_no)]
        return {"hedef": lv["goal"], "durum": lv["durum"], "ara_sonuçlar": lv["sonuç"], "bitti": lv.get("bitti", False)}
    rows = memory._q("SELECT id, goal, status, created, finished FROM team_runs ORDER BY id DESC LIMIT 10")
    return [{"no": r["id"], "hedef": r["goal"][:80], "durum": r["status"], "süre_dk": round(((r["finished"] or time.time()) - r["created"]) / 60, 1)} for r in rows] or "Ekip görevi yok."


def team_performance():
    rows = memory._q("SELECT role, COUNT(*) n, SUM(ok) ok, AVG(seconds) s, SUM(retried) re FROM team_stats GROUP BY role ORDER BY n DESC")
    return [{"rol": r["role"], "görev": r["n"], "başarı_%": round(100 * (r["ok"] or 0) / r["n"]), "ort_süre_sn": round(r["s"] or 0, 1), "düzeltme_istenen": r["re"] or 0} for r in rows] or "Henüz veri yok."


def team_memory(role="", note="", action="list"):
    if action == "add" and role in ROLES and note:
        memory._q("INSERT INTO team_memory(role,note,ts) VALUES(?,?,?)", (role, note, time.time()), commit=True)
        return f"{role} hafızasına eklendi."
    if action == "clear" and role:
        memory._q("DELETE FROM team_memory WHERE role=?", (role,), commit=True)
        return f"{role} hafızası temizlendi."
    q = "SELECT role, note FROM team_memory" + (" WHERE role=?" if role else "") + " ORDER BY id DESC LIMIT 30"
    return memory._q(q, (role,) if role else ()) or "Ekip hafızası boş."


TOOLS = {
    "team_task": (team_task, _schema(
        "Büyük/karmaşık bir hedefi JARVIS EKİBİNE verir: yönetici planlar, uzman ajanlar (araştırmacı, kodcu, güvenlik, görüntü, ses, tasarımcı, robotik, analist, yazar) "
        "bağımlılık sırasıyla paralel çalışır ve sonuçlarını birbirine devreder, denetçi kontrol eder, yetersiz iş yeniden yapılır, birleşik rapor döner. "
        "Kullanıcı önce planı görmek isterse approve_plan=true.",
        {"goal": S("hedef"), "roles": S("sadece bu roller (virgülle, boş: otomatik)"), "approve_plan": {"type": "boolean"}}, ["goal"]), False),
    "team_run": (team_run, _schema("Onaylanan ekip planını çalıştırır.", {"plan_no": {"type": "number"}}, ["plan_no"]), False),
    "team_status": (team_status, _schema("Ekip görevlerinin durumu / canlı ilerleme.", {"run_no": {"type": "number"}}), False),
    "team_performance": (team_performance, _schema("Ajanların performans karşılaştırması (başarı, süre, düzeltme)."), False),
    "team_memory": (team_memory, _schema("Ekip üyelerinin kendi hafızalarını görür / not ekler / temizler.",
                                         {"role": S("rol"), "note": S("not"), "action": {"type": "string", "enum": ["list", "add", "clear"]}}), False),
}
