"""One-off reproducible GPL SweetHomeJS rebuild from retained source and assets.

Fixes the self-appending furniture category bootstrap and preserves constructor
names required by the SH3D XML serializer. Requires Node/npm on the build host.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"


def run(*args, cwd=None):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def main():
    with tempfile.TemporaryDirectory(prefix="jarvis-sweethomejs-rebuild-") as tmp:
        source = Path(tmp) / "sweethomejs"
        source.mkdir()
        with zipfile.ZipFile(VENDOR / "designer-source.zip") as archive:
            archive.extractall(source)

        public = source / "apps" / "web" / "public"
        public.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(VENDOR / "designer.zip") as archive:
            for item in archive.infolist():
                name = item.filename
                if name == "catalog.sh3f" or name.startswith(("help/", "icons/", "fixtures/")):
                    if item.is_dir():
                        continue
                    destination = (public / name).resolve()
                    if not destination.is_relative_to(public.resolve()):
                        raise ValueError("Unexpected public asset path")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(item))
            licenses = source / "src" / "SweetHome3D-7.5-src"
            licenses.mkdir(parents=True, exist_ok=True)
            for item in archive.infolist():
                if item.filename.startswith("licenses/") and not item.is_dir():
                    (licenses / Path(item.filename).name).write_bytes(archive.read(item))
        if not (public / "catalog.sh3f").exists():
            raise RuntimeError("The retained designer archive lacks its furniture catalog")

        bridge = source / "apps" / "web" / "src" / "jarvisBridge.ts"
        code = bridge.read_text(encoding="utf-8")
        pattern = r"for\s*\(const cat of catalog\.getCategories\(\)\)\s*for\s*\(const piece of cat\.getFurniture\(\)\)\s*preferences\.getFurnitureCatalog\(\)\.add\(cat,piece\);"
        fixed = "preferences.getFurnitureCatalog().getCategories().push(...catalog.getCategories());"
        code, count = re.subn(pattern, fixed, code)
        if count != 1:
            if fixed not in code:
                raise RuntimeError("Expected furniture catalog bootstrap code not found")
        bridge.write_text(code, encoding="utf-8")

        vite = source / "apps" / "web" / "vite.config.ts"
        vite_text = vite.read_text(encoding="utf-8")
        if "keepNames" not in vite_text:
            marker = "export default defineConfig({"
            if marker not in vite_text:
                raise RuntimeError("Vite configuration shape changed")
            vite_text = vite_text.replace(
                marker,
                marker + "\n  // SH3D XML uses constructor.name to identify all model types.\n  esbuild: { keepNames: true },",
                1,
            )
            vite.write_text(vite_text, encoding="utf-8")

        run("npm", "ci", "--no-audit", "--no-fund", cwd=source)
        for name in (
            "@sweethomejs/core",
            "@sweethomejs/render2d",
            "@sweethomejs/render3d",
            "@sweethomejs/export",
            "@sweethomejs/photo",
            "@sweethomejs/ui",
        ):
            run("npm", "run", "build", "-w", name, cwd=source)
        run("npm", "run", "build", "-w", "@sweethomejs/web", "--", "--base=/designer/", cwd=source)
        run(sys.executable, ROOT / "scripts" / "package_designer.py", source)
        manifest = json.loads((VENDOR / "designer.json").read_text(encoding="utf-8"))
        manifest["catalog_fix"] = "shared-categories-source"
        manifest["xml_constructor_names"] = "preserved-vite-esbuild"
        (VENDOR / "designer.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with zipfile.ZipFile(VENDOR / "designer.zip") as archive:
            js = [i for i in archive.infolist() if i.filename.startswith("assets/index-") and i.filename.endswith(".js")]
            if not js or "catalog.sh3f" not in archive.namelist():
                raise RuntimeError("Designer build output lacks its JS entry point or model catalog")
            print("New designer ZIP:", (VENDOR / "designer.zip").stat().st_size, "bytes", flush=True)
        print("Reproducible source ZIP:", (VENDOR / "designer-source.zip").stat().st_size, "bytes", flush=True)


if __name__ == "__main__":
    main()
