"""Yetenek modülleri. Her modül bir TOOLS sözlüğü verir: {ad: (fonksiyon, şema, kritik_mi)}.

plugins/ klasörüne aynı biçimde bir .py dosyası koyarsan JARVIS açılışta onu da yükler.
"""
import importlib
import importlib.util
import traceback

from ..config import ROOT

MODULES = ["google", "computer", "windows", "office", "finance", "automation", "smarthome", "media", "voiceid", "vault", "habits", "games", "selfdev", "semantic", "geo", "holo", "control", "daily", "space", "worldwatch", "team", "translate", "studio", "command", "world", "knowledge", "nodes", "twin", "financelab", "music", "browser", "arfx", "cams", "library", "scene", "life", "hud", "stage"]
LOAD_ERRORS = {}


def load_all():
    """(araçlar, araç→grup) döner."""
    tools, groups = {}, {}
    for name in MODULES:
        try:
            mod = importlib.import_module(f"{__name__}.{name}")
            t = getattr(mod, "TOOLS", {})
            for k in t:
                if k in tools:  # aynı adlı iki araç: sessizce ezilmesin
                    print(f"[yetenek] UYARI: '{k}' aracı {name} modülünde tekrar tanımlanmış (öncekinin üzerine yazıldı)")
                    LOAD_ERRORS[f"dup:{k}"] = name
            tools.update(t)
            groups.update({k: getattr(mod, "GROUP", name) for k in t})  # modül GROUP ile başka grubun parçası olabilir
        except Exception:
            LOAD_ERRORS[name] = traceback.format_exc(limit=2)
            print(f"[yetenek] {name} yüklenemedi:\n{LOAD_ERRORS[name]}")
    pt, pg = load_plugins()
    tools.update(pt)
    groups.update(pg)
    return tools, groups


def load_plugins():
    tools, groups = {}, {}
    for k in [k for k in LOAD_ERRORS if k.startswith("plugin:")]:
        LOAD_ERRORS.pop(k)
    plug_dir = ROOT / "plugins"
    plug_dir.mkdir(exist_ok=True)
    for f in sorted(plug_dir.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            t = getattr(mod, "TOOLS", {})
            tools.update(t)
            groups.update({k: "plugins" for k in t})
            print(f"[eklenti] yüklendi: {f.name}")
        except Exception:
            LOAD_ERRORS[f"plugin:{f.name}"] = traceback.format_exc(limit=2)
            print(f"[eklenti] {f.name} yüklenemedi")
    return tools, groups
