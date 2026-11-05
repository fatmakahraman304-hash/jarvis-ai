"""Kendi kendini geliştirme: kendi kodunu okuma, yeni yetenek (eklenti) yazıp TEST ETTİKTEN sonra etkinleştirme,
güncellemeleri kontrol etme, güvenli güncelleme ve hata olursa otomatik geri alma.

Kural: JARVIS kendi kodunu test etmeden ve senin onayın olmadan değiştirmez."""
import json
import re
import subprocess
import sys
import time

from ..config import ROOT
from ..tools import S, _schema

PLUGINS = ROOT / "plugins"
STAGING = ROOT / "plugins" / "_deneme"

VALIDATOR = r'''
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("p", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
T = getattr(m, "TOOLS", None)
assert isinstance(T, dict) and T, "TOOLS sözlüğü yok veya boş"
for k, v in T.items():
    assert isinstance(k, str) and k.isidentifier(), f"geçersiz araç adı: {k}"
    fn, sch, crit = v
    assert callable(fn), f"{k}: fonksiyon değil"
    assert "description" in sch and sch.get("parameters", {}).get("type") == "object", f"{k}: şema hatalı"
print(json.dumps(sorted(T)))
'''


def list_own_code():
    files = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(x in p.parts for x in (".venv", "__pycache__", "_deneme")):
            continue
        files.append({"dosya": str(p.relative_to(ROOT)), "satır": sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))})
    return files


def read_own_code(path, start=1, lines=200):
    p = (ROOT / path).resolve()
    if ROOT.resolve() not in p.parents or p.suffix not in (".py", ".js", ".html", ".css", ".md", ".txt", ".bat"):
        return "Sadece JARVIS klasöründeki kod dosyaları okunabilir."
    allines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    s = max(1, int(start))
    chunk = allines[s - 1: s - 1 + int(lines)]
    return "\n".join(f"{i:4d}  {ln}" for i, ln in enumerate(chunk, s)) + (f"\n... (toplam {len(allines)} satır)" if s - 1 + int(lines) < len(allines) else "")


def create_plugin(name, code):
    """Yeni yetenek: önce deneme klasörüne yazar, ayrı süreçte yükleyip doğrular, sonra etkinleştirir."""
    name = re.sub(r"\W+", "_", name.lower()).strip("_")
    if not name:
        return "Geçersiz ad."
    banned = [r"\bshutil\.rmtree\s*\(\s*['\"][A-Za-z]:\\\\?['\"]", r"format\s+c:", r"\brm\s+-rf\s+/"]
    if any(re.search(b, code, re.I) for b in banned):
        return "Kod tehlikeli bir işlem içeriyor, reddedildi."
    STAGING.mkdir(parents=True, exist_ok=True)
    tmp = STAGING / f"{name}.py"
    tmp.write_text(code, encoding="utf-8")
    r = subprocess.run([sys.executable, "-c", VALIDATOR, str(tmp)], capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip().splitlines()[-6:]
        return {"durum": "TEST BAŞARISIZ, etkinleştirilmedi", "hata": "\n".join(err),
                "not": "Hatayı düzeltip create_plugin'i tekrar çağır."}
    final = PLUGINS / f"{name}.py"
    if final.exists():
        backup = PLUGINS / "_yedek"
        backup.mkdir(exist_ok=True)
        final.replace(backup / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.py")
    tmp.replace(final)
    from .. import tools
    added = tools.reload_plugins()
    return {"durum": "test geçti, etkinleştirildi", "eklenti": final.name, "yeni_araçlar": json.loads(r.stdout.strip() or "[]"),
            "yüklenen_toplam_eklenti_aracı": added}


def remove_plugin(name):
    stem = re.sub(r"\W+", "_", name.lower()).strip("_")
    p = PLUGINS / f"{stem}.py"
    if not p.exists():
        return "Böyle bir eklenti yok."
    backup = PLUGINS / "_yedek"
    backup.mkdir(exist_ok=True)
    p.replace(backup / f"{p.stem}_{time.strftime('%Y%m%d_%H%M%S')}.py")
    from .. import tools
    tools.reload_plugins()
    return f"Eklenti kaldırıldı (yedeği plugins/_yedek içinde): {p.name}"


def list_plugins():
    return [p.name for p in sorted(PLUGINS.glob("*.py"))] or "Eklenti yok."


def _git(*args, timeout=60):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="ignore")
    return r.returncode, (r.stdout + r.stderr).strip()


def check_updates():
    if not (ROOT / ".git").exists():
        return "Bu klasör bir git deposu değil. GitHub deponu klonlarsan güncellemeleri buradan kontrol edebilirim."
    code, out = _git("fetch", "--quiet")
    if code:
        return f"Güncelleme kontrol edilemedi: {out[:300]}"
    _, branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    _, behind = _git("rev-list", "--count", f"HEAD..@{{u}}")
    _, log = _git("log", "--oneline", f"HEAD..@{{u}}", "-n", "15")
    _, dirty = _git("status", "--porcelain")
    return {"dal": branch, "yeni_değişiklik": int(behind) if behind.isdigit() else behind,
            "değişiklikler": log.splitlines(), "yerel_kaydedilmemiş_değişiklik": bool(dirty.strip())}


def apply_update():
    if not (ROOT / ".git").exists():
        return "Git deposu değil."
    tag = f"jarvis-yedek-{time.strftime('%Y%m%d-%H%M%S')}"
    _, dirty = _git("status", "--porcelain")
    if dirty.strip():
        _git("stash", "push", "-u", "-m", tag)
    _git("tag", tag)
    code, out = _git("pull", "--ff-only", timeout=180)
    if code:
        return f"Güncelleme alınamadı: {out[:300]}"
    tests = [ROOT / "tests" / "test_smoke.py", ROOT / "tests" / "test_skills.py"]
    for t in tests:
        if not t.exists():
            continue
        r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True, timeout=300, encoding="utf-8", errors="ignore")
        if r.returncode != 0:
            _git("reset", "--hard", tag)
            return {"durum": "Yeni sürüm testleri GEÇEMEDİ, otomatik olarak eski sürüme geri dönüldü.",
                    "test": t.name, "çıktı": r.stdout[-800:]}
    return {"durum": "Güncellendi ve testler geçti. Değişikliklerin etkinleşmesi için JARVIS'i yeniden başlat.",
            "geri_alma_noktası": tag, "çıktı": out[-300:]}


def rollback_update(tag=""):
    if not tag:
        _, tags = _git("tag", "--list", "jarvis-yedek-*", "--sort=-creatordate")
        tag = (tags.splitlines() or [""])[0]
    if not tag:
        return "Geri dönülecek yedek yok."
    code, out = _git("reset", "--hard", tag)
    return f"{tag} sürümüne geri dönüldü. JARVIS'i yeniden başlat." if not code else out


TOOLS = {
    "list_own_code": (list_own_code, _schema("JARVIS'in kendi kod dosyalarını listeler."), False),
    "read_own_code": (read_own_code, _schema("JARVIS'in kendi kodunu okur (analiz/hata bulma için).",
                                             {"path": S("dosya, örn core/brain.py"), "start": {"type": "number"}, "lines": {"type": "number"}}, ["path"]), False),
    "create_plugin": (create_plugin, _schema(
        "Yeni yetenek ekler: Python eklentisi yazar, test eder, geçerse etkinleştirir (onay gerekir). Kod şu biçimde olmalı: "
        "fonksiyonlar + TOOLS = {'ad': (fonksiyon, {'description': '...', 'parameters': {'type': 'object', 'properties': {...}, 'required': [...]}}, kritik_mi)}. "
        "Sadece standart kütüphane veya kurulu paketleri kullan.",
        {"name": S("eklenti adı"), "code": S("tam Python kodu")}, ["name", "code"]), True),
    "remove_plugin": (remove_plugin, _schema("Bir eklentiyi kaldırır (yedeklenir).", {"name": S("eklenti adı")}, ["name"]), True),
    "list_plugins": (list_plugins, _schema("Yüklü eklentiler."), False),
    "check_updates": (check_updates, _schema("GitHub'da yeni sürüm var mı kontrol eder."), False),
    "apply_update": (apply_update, _schema("Güncellemeyi alır, testleri çalıştırır; testler geçmezse otomatik geri alır."), True),
    "rollback_update": (rollback_update, _schema("Önceki sürüme geri döner.", {"tag": S("yedek etiketi (boş=son)")}), True),
}
