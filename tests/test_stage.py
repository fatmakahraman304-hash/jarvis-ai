"""Orta sahne araçları (animasyon, sahneyi kapat, çekirdek görünümü) ve grup yönlendirmesi.  python tests/test_stage.py"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_stage_")
from core import tools  # noqa: E402
from core.skills import stage  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


r = stage.stage_animation("güneş sistemi")
check("başlıktan hazır animasyon seçilir", r.get("ui") == "stage" and r.get("preset") == "solar", r)
r = stage.stage_animation("x", preset="DNA")
check("hazır ad büyük harfle de çalışır", r.get("preset") == "dna", r)
r = stage.stage_animation("özel", code="function draw(t,w,h){}")
check("özel kodda preset boş, ui stage", r.get("ui") == "stage" and r.get("preset") == "", r)
check("kod sonuca kopyalanmaz (model bağlamı şişmez)", "code" not in r)
check("ne hazır ne kod: anlaşılır hata", "error" in stage.stage_animation("bilinmeyen şey"))
check("çok uzun kod reddedilir", "error" in stage.stage_animation("x", code="a" * 70000))
check("sahneyi kapat", stage.stage_clear() == {"ui": "stage", "kind": "clear"})
check("çekirdek görünümü: dalga → wave", stage.core_style("dalga") == {"ui": "core", "style": "wave"})
check("geçersiz görünüm hata", "error" in stage.core_style("üçgen"))
check("'animasyon' sözcüğü stage grubunu açar", "stage" in tools.pick_groups("bana bir atom animasyonu göster"))
check("'youtube video aç' media grubunu açar", "media" in tools.pick_groups("youtubedan video aç"))
names = [s["function"]["name"] for s in tools.specs({"stage", "core"})]
check("araçlar kayıtlı", all(n in names for n in ("stage_animation", "stage_clear", "core_style")), names[-5:])
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
