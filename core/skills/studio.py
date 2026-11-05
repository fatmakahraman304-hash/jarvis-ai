"""Görsel stüdyo: yapay zekâ ile resim üretme (Pollinations, anahtarsız; HF_TOKEN varsa FLUX yedeği), fotoğraf düzenleme ve kolaj (Pillow),
vektör logo üretimi (SVG + PNG), video bilgisi / sahne değişimi / içerik analizi / kesme / birleştirme / altyazı gömme / GIF / slayt montajı (ffmpeg)."""
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import env
from ..tools import HOME, S, _path, _schema

OUT = HOME / "Pictures" / "JARVIS"
VOUT = HOME / "Videos" / "JARVIS"
UA = "JARVIS-Studio/3.0"
STYLES = {"": "", "gerçekçi": "photorealistic, 8k, detailed", "sinematik": "cinematic lighting, film still, dramatic",
          "anime": "anime style, studio quality", "çizgi film": "cartoon style, colorful", "yağlı boya": "oil painting, brush strokes",
          "suluboya": "watercolor painting", "3d": "3d render, octane, studio lighting", "piksel": "pixel art, 16-bit",
          "siberpunk": "cyberpunk, neon lights, futuristic", "minimal": "minimalist, flat design, clean", "eskiz": "pencil sketch, line art",
          "hologram": "holographic blue glowing interface, sci-fi, Iron Man JARVIS style"}


def _out(name, folder=OUT):
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


def _slug(t, n=40):
    s = re.sub(r"[^\w]+", "_", t.lower(), flags=re.U).strip("_")[:n]
    return s or "resim"


# ---------------- yapay zekâ ile resim ----------------

def _pollinations(prompt, w, h, seed, model):
    q = {"width": w, "height": h, "seed": seed, "nologo": "true", "model": model or "flux", "enhance": "true"}
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?" + urllib.parse.urlencode(q)
    hdr = {"User-Agent": UA}
    if env("POLLINATIONS_TOKEN"):
        hdr["Authorization"] = "Bearer " + env("POLLINATIONS_TOKEN")
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=150) as r:
        if not r.headers.get("Content-Type", "").startswith("image"):
            raise RuntimeError("resim yerine " + r.headers.get("Content-Type", "?") + " döndü")
        return r.read()


def _hf(prompt, w, h, seed):
    key = env("HF_TOKEN")
    if not key:
        raise RuntimeError("HF_TOKEN yok")
    url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    body = json.dumps({"inputs": prompt, "parameters": {"width": w, "height": h, "seed": seed}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "image/png"})
    with urllib.request.urlopen(req, timeout=150) as r:
        return r.read()


def image_generate(prompt, style="", width=1024, height=1024, seed=0, count=1):
    """Metinden resim üretir. İstem Türkçe olabilir (model İngilizceye çevirir); stil eklenebilir."""
    w, h = max(256, min(int(width or 1024), 2048)), max(256, min(int(height or 1024), 2048))
    full = prompt + (", " + STYLES.get(style.lower(), style) if style else "")
    files, errs = [], []
    for i in range(max(1, min(int(count or 1), 4))):
        sd = int(seed or 0) + i if seed else random.randint(1, 2_000_000_000)
        data = None
        for name, fn in (("pollinations", lambda: _pollinations(full, w, h, sd, "flux")), ("huggingface", lambda: _hf(full, w, h, sd))):
            try:
                data = fn()
                break
            except Exception as e:
                errs.append(f"{name}: {e}")
        if not data:
            break
        ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
        p = _out(f"{time.strftime('%Y%m%d_%H%M%S')}_{_slug(prompt)}_{sd}{ext}")
        p.write_bytes(data)
        files.append(str(p))
    if not files:
        return "Resim üretilemedi (internet/servis sorunu): " + "; ".join(errs[-2:]) + ". Ücretsiz yedek için .env'e HF_TOKEN ekleyebilirsin."
    return {"ui": "image", "path": files[0], "files": files, "title": prompt[:80], "kind": "image", "boyut": f"{w}x{h}"}


# ---------------- fotoğraf düzenleme ----------------

def _pil():
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps  # noqa: F401
        return __import__("PIL.Image").Image
    except ImportError:
        raise RuntimeError("Fotoğraf düzenleme için 'pip install pillow' gerekli.")


def _font(size):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def photo_edit(path, operations, output=""):
    """İşlemler virgülle: resize:800x600, width:1200, crop:x,y,w,h, crop_center:1:1, rotate:90, flip, mirror, brightness:1.2, contrast:1.3,
    saturation:0.5, sharpen, blur:3, grayscale, sepia, invert, autocontrast, vignette, border:20:#000000, text:Merhaba:bottom, watermark:© Ben,
    remove_bg:#ffffff (düz renkli arka planı saydam yapar), format:webp, quality:85"""
    _pil()
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    im = ImageOps.exif_transpose(Image.open(p))
    fmt, quality, done = p.suffix.lstrip(".").lower() or "png", 92, []
    for op in _split_ops(operations):
        name, _, arg = op.partition(":")
        name = name.strip().lower()
        try:
            if name == "resize":
                w, h = [int(x) for x in arg.lower().split("x")]
                im = im.resize((w, h), Image.LANCZOS)
            elif name == "width":
                w = int(arg); im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            elif name == "height":
                h = int(arg); im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
            elif name == "crop":
                x, y, w, h = [int(float(v)) for v in arg.split(",")]
                im = im.crop((x, y, x + w, y + h))
            elif name == "crop_center":
                a, b = [float(v) for v in arg.split(":")] if ":" in arg else (1, 1)
                tw = min(im.width, im.height * a / b); th = tw * b / a
                l, t = (im.width - tw) / 2, (im.height - th) / 2
                im = im.crop((round(l), round(t), round(l + tw), round(t + th)))
            elif name == "rotate":
                im = im.rotate(-float(arg or 90), expand=True)
            elif name == "flip":
                im = ImageOps.flip(im)
            elif name == "mirror":
                im = ImageOps.mirror(im)
            elif name in ("brightness", "contrast", "saturation", "sharpness"):
                cls = {"brightness": ImageEnhance.Brightness, "contrast": ImageEnhance.Contrast, "saturation": ImageEnhance.Color, "sharpness": ImageEnhance.Sharpness}[name]
                im = cls(im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im).enhance(float(arg or 1.2))
            elif name == "sharpen":
                im = im.filter(ImageFilter.UnsharpMask(2, 150, 3))
            elif name == "blur":
                im = im.filter(ImageFilter.GaussianBlur(float(arg or 2)))
            elif name in ("grayscale", "gri", "siyah_beyaz"):
                im = ImageOps.grayscale(im).convert("RGB")
            elif name == "sepia":
                g = ImageOps.grayscale(im)
                im = ImageOps.colorize(g, "#2b1a0e", "#f3e3c3", mid="#a67c52")
            elif name == "invert":
                im = ImageOps.invert(im.convert("RGB"))
            elif name == "autocontrast":
                im = ImageOps.autocontrast(im.convert("RGB"), cutoff=1)
            elif name == "vignette":
                mask = Image.new("L", im.size, 0); d = ImageDraw.Draw(mask)
                d.ellipse((-im.width * 0.15, -im.height * 0.15, im.width * 1.15, im.height * 1.15), fill=255)
                mask = mask.filter(ImageFilter.GaussianBlur(min(im.size) / 6))
                im = Image.composite(im.convert("RGB"), Image.new("RGB", im.size, "black"), mask)
            elif name == "border":
                parts = arg.split(":")
                im = ImageOps.expand(im.convert("RGB"), int(parts[0] or 20), fill=parts[1] if len(parts) > 1 else "#000000")
            elif name in ("text", "watermark"):
                parts = arg.split(":")
                txt, pos = parts[0], (parts[1] if len(parts) > 1 else ("bottomright" if name == "watermark" else "bottom"))
                im = im.convert("RGBA")
                layer = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
                size = max(14, im.width // (28 if name == "watermark" else 14)); f = _font(size)
                bb = d.textbbox((0, 0), txt, font=f); tw, th = bb[2] - bb[0], bb[3] - bb[1]; m = size // 2
                x = {"left": m, "topleft": m, "bottomleft": m, "right": im.width - tw - m, "topright": im.width - tw - m, "bottomright": im.width - tw - m}.get(pos, (im.width - tw) // 2)
                y = m if pos.startswith("top") else ((im.height - th) // 2 if pos == "center" else im.height - th - m * 2)
                alpha = 140 if name == "watermark" else 255
                d.text((x + 2, y + 2), txt, font=f, fill=(0, 0, 0, alpha))
                d.text((x, y), txt, font=f, fill=(255, 255, 255, alpha))
                im = Image.alpha_composite(im, layer)
            elif name == "remove_bg":
                col = arg or "#ffffff"
                rgb = tuple(int(col.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                im = im.convert("RGBA"); px = im.load(); tol = 40
                for yy in range(im.height):
                    for xx in range(im.width):
                        r, g, b, a = px[xx, yy]
                        if abs(r - rgb[0]) + abs(g - rgb[1]) + abs(b - rgb[2]) < tol:
                            px[xx, yy] = (r, g, b, 0)
                fmt = "png"
            elif name == "format":
                fmt = arg.lower().replace("jpeg", "jpg")
            elif name == "quality":
                quality = int(arg)
            else:
                return f"Bilinmeyen işlem: {name}"
            done.append(op)
        except Exception as e:
            return f"'{op}' uygulanamadı: {e}"
    out = _path(output) if output else p.with_name(f"{p.stem}_duzenlendi.{fmt}")
    if fmt in ("jpg", "jpeg") and im.mode != "RGB":
        im = im.convert("RGB")
    im.save(out, {"jpg": "JPEG"}.get(fmt, fmt.upper()), quality=quality)
    return {"ui": "image", "path": str(out), "title": "Düzenlendi: " + ", ".join(done), "kind": "image", "boyut": f"{im.width}x{im.height}"}


def _split_ops(s):
    """'crop:10,20,300,200,grayscale' gibi virgüllü argümanları doğru böler."""
    out, cur = [], ""
    for tok in s.split(","):
        if cur and (re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", tok) and cur.split(":")[0].strip() == "crop" and cur.count(",") < 3):
            cur += "," + tok
        else:
            if cur:
                out.append(cur.strip())
            cur = tok
    if cur:
        out.append(cur.strip())
    return out


def photo_collage(paths, columns=0, gap=8, width=1800, output=""):
    _pil()
    from PIL import Image, ImageOps
    files = [_path(x) for x in (paths if isinstance(paths, list) else str(paths).split(";"))]
    files = [f for f in files if f.exists()]
    if not files:
        return "Resim bulunamadı."
    cols = int(columns) or math.ceil(math.sqrt(len(files)))
    rows = math.ceil(len(files) / cols)
    cell = (int(width) - gap * (cols + 1)) // cols
    sheet = Image.new("RGB", (int(width), rows * cell + gap * (rows + 1)), "#0b0f14")
    for i, f in enumerate(files):
        im = ImageOps.fit(ImageOps.exif_transpose(Image.open(f)).convert("RGB"), (cell, cell))
        sheet.paste(im, (gap + (i % cols) * (cell + gap), gap + (i // cols) * (cell + gap)))
    out = _path(output) if output else _out(f"kolaj_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
    sheet.save(out, quality=90)
    return {"ui": "image", "path": str(out), "title": f"Kolaj ({len(files)} resim)", "kind": "image"}


# ---------------- logo ----------------

PALETTES = [("#38d6ff", "#0a6cff"), ("#ff6b35", "#f7c59f"), ("#16db93", "#048ba8"), ("#e63946", "#1d3557"), ("#9b5de5", "#f15bb5"),
            ("#ffd60a", "#003566"), ("#2ec4b6", "#011627"), ("#f72585", "#3a0ca3")]


def _initials(name):
    w = [x for x in re.split(r"\s+", name.strip()) if x]
    return ("".join(x[0] for x in w[:2]) if len(w) > 1 else name[:2]).upper()


def _logo_svg(name, slogan, shape, c1, c2, font):
    ini = _initials(name)
    defs = f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
    icon = {
        "daire": '<circle cx="110" cy="110" r="80" fill="url(#g)"/>',
        "altıgen": '<polygon points="110,28 181,69 181,151 110,192 39,151 39,69" fill="url(#g)"/>',
        "kalkan": '<path d="M110 26 L182 52 L176 128 Q160 172 110 196 Q60 172 44 128 L38 52 Z" fill="url(#g)"/>',
        "elmas": '<polygon points="110,26 194,110 110,194 26,110" fill="url(#g)"/>',
        "halka": f'<circle cx="110" cy="110" r="74" fill="none" stroke="url(#g)" stroke-width="16"/><circle cx="110" cy="110" r="46" fill="{c1}" opacity=".18"/>',
        "kare": '<rect x="34" y="34" width="152" height="152" rx="34" fill="url(#g)"/>',
    }.get(shape, '<circle cx="110" cy="110" r="80" fill="url(#g)"/>')
    tcol = c1 if shape == "halka" else "#ffffff"
    sub = f'<text x="236" y="150" font-family="{font}" font-size="24" letter-spacing="4" fill="#8aa0b4">{_esc(slogan.upper())}</text>' if slogan else ""
    width = max(560, 260 + 30 * len(name))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="220" viewBox="0 0 {width} 220">{defs}{icon}'
            f'<text x="110" y="128" text-anchor="middle" font-family="{font}" font-size="{60 if len(ini) > 1 else 78}" font-weight="800" fill="{tcol}">{_esc(ini)}</text>'
            f'<text x="236" y="{110 if slogan else 128}" font-family="{font}" font-size="56" font-weight="800" fill="url(#g)">{_esc(name)}</text>{sub}</svg>')


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def logo_make(name, slogan="", shape="", colors="", count=4):
    """Vektör logo varyantları (SVG, her boyutta keskin) + PNG önizleme. Şekiller: daire, altıgen, kalkan, elmas, halka, kare. Renk: '#hex,#hex'."""
    shapes = [shape] if shape else ["altıgen", "kalkan", "halka", "kare", "daire", "elmas"]
    rnd = random.Random(hashlib.md5(name.encode()).hexdigest())
    pals = [tuple(c.strip() for c in colors.split(","))[:2]] if colors and "," in colors else rnd.sample(PALETTES, len(PALETTES))
    folder = OUT / f"logo_{_slug(name, 24)}"
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(max(1, min(int(count or 4), 6))):
        sh, (c1, c2) = shapes[i % len(shapes)], pals[i % len(pals)]
        svg = _logo_svg(name, slogan, sh, c1, c2, "Segoe UI, Montserrat, Arial, sans-serif")
        p = folder / f"{_slug(name, 24)}_{i + 1}_{sh}.svg"
        p.write_text(svg, encoding="utf-8")
        files.append(str(p))
    png = _logo_png(name, slogan, shapes[0], pals[0], folder / f"{_slug(name, 24)}_onizleme.png")
    return {"ui": "image", "path": png or files[0], "files": files, "title": f"{name} logoları ({len(files)} SVG)", "kind": "image", "klasör": str(folder),
            "not": "SVG dosyaları vektördür (baskı/web için büyütülebilir). Yapay zekâ ile resimsel logo için image_generate'i 'minimal logo' stiliyle kullan."}


def _logo_png(name, slogan, shape, pal, out):
    try:
        _pil()
        from PIL import Image, ImageDraw
    except Exception:
        return ""
    c1, c2 = pal
    lum = lambda c: sum(int(c.lstrip("#")[k:k + 2], 16) * w for k, w in ((0, .299), (2, .587), (4, .114)))
    dark = c1 if lum(c1) < lum(c2) else c2
    ft0 = _font(110)
    tb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), name, font=ft0)
    W, H = 440 + (tb[2] - tb[0]) + 80, 440
    im = Image.new("RGBA", (W, H), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    grad = Image.new("RGBA", (360, 360)); gd = ImageDraw.Draw(grad)
    a, b = [tuple(int(c.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4)) for c in (c1, c2)]
    for y in range(360):
        t = y / 359
        gd.line([(0, y), (359, y)], fill=tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3)) + (255,))
    mask = Image.new("L", (360, 360), 0); md = ImageDraw.Draw(mask)
    if shape == "altıgen":
        md.polygon([(180, 10), (336, 95), (336, 265), (180, 350), (24, 265), (24, 95)], fill=255)
    elif shape in ("kare", "kalkan"):
        md.rounded_rectangle((20, 20, 340, 340), 70, fill=255)
    elif shape == "elmas":
        md.polygon([(180, 10), (350, 180), (180, 350), (10, 180)], fill=255)
    elif shape == "halka":
        md.ellipse((20, 20, 340, 340), fill=255); md.ellipse((62, 62, 298, 298), fill=0)
    else:
        md.ellipse((20, 20, 340, 340), fill=255)
    im.paste(grad, (40, 40), mask)
    f, ft, fs = _font(140 if len(_initials(name)) > 1 else 170), _font(110), _font(40)
    ini = _initials(name)
    bb = d.textbbox((0, 0), ini, font=f)
    d.text((220 - (bb[2] - bb[0]) / 2 - bb[0], 220 - (bb[3] - bb[1]) / 2 - bb[1]), ini, font=f, fill=c1 if shape == "halka" else "white")
    d.text((440, 120 if slogan else 160), name, font=ft, fill=dark)
    if slogan:
        d.text((446, 260), slogan.upper(), font=fs, fill="#8aa0b4")
    bbox = im.getbbox()
    im = im.crop((0, 0, min(W, (bbox[2] if bbox else W) + 40), H))
    im.save(out)
    return str(out)


# ---------------- video (ffmpeg) ----------------

def _ff(tool="ffmpeg"):
    p = shutil.which(tool)
    if p:
        return p
    for base in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages", Path("C:/ffmpeg/bin"), Path("C:/Program Files/ffmpeg/bin")):
        if base.exists():
            for c in base.rglob(f"{tool}.exe"):
                return str(c)
    raise RuntimeError("ffmpeg bulunamadı. Kur: winget install Gyan.FFmpeg (ya da 'JARVIS ffmpeg kur' de).")


def _run(args, timeout=900):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-600:])
    return r


def video_info(path):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    j = json.loads(_run([_ff("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(p)]).stdout)
    fmt = j.get("format", {})
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    fps = v.get("avg_frame_rate", "0/1")
    try:
        n, d = fps.split("/"); fps = round(int(n) / int(d), 2) if int(d) else 0
    except Exception:
        pass
    return {"dosya": p.name, "süre_sn": round(float(fmt.get("duration", 0)), 2), "boyut_MB": round(int(fmt.get("size", 0)) / 1e6, 2),
            "çözünürlük": f"{v.get('width')}x{v.get('height')}" if v else "yok", "fps": fps, "video_kodek": v.get("codec_name"),
            "ses": f"{a.get('codec_name')} {a.get('sample_rate')} Hz {a.get('channels')} kanal" if a else "yok", "bit_hızı_kbps": round(int(fmt.get("bit_rate", 0)) / 1000)}


def video_scenes(path, threshold=0.3, thumbnails=True):
    """Sahne değişimlerini bulur (ffmpeg scene filtresi), her sahne için küçük resim çıkarır."""
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    r = _run([_ff(), "-hide_banner", "-i", str(p), "-vf", f"select='gt(scene,{float(threshold)})',showinfo", "-an", "-f", "null", "-"])
    times = [0.0] + [round(float(m), 2) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    times = [t for i, t in enumerate(times) if i == 0 or t - times[i - 1] > 0.5]
    res = {"sahne_sayısı": len(times), "sahne_başlangıçları_sn": times[:200]}
    if thumbnails and times:
        folder = VOUT / f"{p.stem}_sahneler"
        folder.mkdir(parents=True, exist_ok=True)
        thumbs = []
        for i, t in enumerate(times[:24]):
            o = folder / f"sahne_{i + 1:02d}_{t:.1f}s.jpg"
            try:
                _run([_ff(), "-y", "-ss", str(t + 0.1), "-i", str(p), "-frames:v", "1", "-vf", "scale=480:-2", str(o)], 60)
                thumbs.append(str(o))
            except Exception:
                pass
        res["küçük_resimler"] = folder.as_posix()
        if thumbs:
            sheet = photo_collage(thumbs, 0, 6, 1600, str(folder / "sahneler.jpg"))
            if isinstance(sheet, dict):
                res.update({"ui": "image", "path": sheet["path"], "title": f"{p.name}: {len(times)} sahne", "kind": "image"})
    return res


def _frames(p, n):
    dur = float(video_info(str(p))["süre_sn"] or 0)
    tmp = Path(tempfile.mkdtemp(prefix="jv_frames_"))
    out = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        o = tmp / f"f{i:02d}.jpg"
        try:
            _run([_ff(), "-y", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=512:-2", str(o)], 60)
            out.append((t, o))
        except Exception:
            pass
    return out, dur


def video_analyze(path, question="Bu videoda ne oluyor? Önemli anları ve kişileri/nesneleri anlat.", frames=9, with_audio=True):
    """Videodan eşit aralıklı kareler alır (zaman damgalı kontakt sayfası) + konuşmayı yazıya döker → görme modeline sorar."""
    from .. import llm
    from PIL import ImageDraw
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    fr, dur = _frames(p, max(4, min(int(frames or 9), 16)))
    if not fr:
        return "Videodan kare alınamadı."
    sheet = photo_collage([str(f) for _, f in fr], 0, 4, 1536, str(fr[0][1].parent / "sheet.jpg"))
    from PIL import Image
    im = Image.open(sheet["path"]); d = ImageDraw.Draw(im)
    cols = math.ceil(math.sqrt(len(fr))); cell = (1536 - 4 * (cols + 1)) // cols
    for i, (t, _) in enumerate(fr):
        x, y = 4 + (i % cols) * (cell + 4), 4 + (i // cols) * (cell + 4)
        d.rectangle((x, y, x + 120, y + 34), fill="black"); d.text((x + 6, y + 4), f"{int(t // 60)}:{int(t % 60):02d}", font=_font(24), fill="#38d6ff")
    im.save(sheet["path"], quality=88)
    speech = ""
    if str(with_audio).lower() not in ("false", "0"):
        try:
            a = fr[0][1].parent / "ses.mp3"
            _run([_ff(), "-y", "-i", str(p), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-t", "1500", str(a)], 300)
            from .media import transcribe_verbose
            speech, _, _ = transcribe_verbose(a.read_bytes(), "ses.mp3", "audio/mpeg", "")
        except Exception as e:
            speech = f"(konuşma alınamadı: {str(e)[:80]})"
    prompt = (f"Bu görsel {dur:.0f} saniyelik bir videonun zaman damgalı {len(fr)} karesinden oluşan bir kontakt sayfası (soldan sağa, yukarıdan aşağı)."
              + (f"\nVideodaki konuşma metni: {speech[:4000]}" if speech else "") + f"\n\nSoru: {question}\nTürkçe yanıtla, zaman damgalarına atıf yap.")
    ans = llm.vision(prompt, Path(sheet["path"]).read_bytes(), "image/jpeg")
    keep = _out(f"{p.stem}_analiz.jpg", VOUT)
    shutil.copy(sheet["path"], keep)
    return {"analiz": ans, "süre_sn": round(dur, 1), "konuşma": speech[:1500], "ui": "image", "path": str(keep), "title": f"{p.name} analizi", "kind": "image"}


def video_edit(path, action, start="", end="", value="", output=""):
    """Video işlemleri: cut (start,end), speed (value=2 hızlı / 0.5 yavaş), resize (value=1280), mute, extract_audio, to_gif (start,end),
    rotate (value=90), compress (value=28 kalite), subtitles (value=srt yolu, gömülü), add_music (value=müzik yolu), reverse, thumbnail (start)."""
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    ff = _ff()
    a = action.lower().strip()
    ext = {"extract_audio": ".mp3", "to_gif": ".gif", "thumbnail": ".jpg"}.get(a, p.suffix or ".mp4")
    out = _path(output) if output else _out(f"{p.stem}_{a}{ext}", VOUT)
    ss = ["-ss", str(start)] if start not in ("", None) else []
    to = ["-to", str(end)] if end not in ("", None) else []
    if a == "cut":
        cmd = [ff, "-y", *ss, *to, "-i", str(p), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", str(out)]
        if start not in ("", None) and end not in ("", None):  # -to giriş öncesi -ss ile göreli değil mutlak çalışsın
            cmd = [ff, "-y", "-ss", str(start), "-i", str(p), "-t", str(_sec(end) - _sec(start)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", str(out)]
    elif a == "speed":
        k = float(value or 2)
        at = []
        r = k
        while r > 2:
            at.append("atempo=2.0"); r /= 2
        while r < 0.5:
            at.append("atempo=0.5"); r /= 0.5
        at.append(f"atempo={r:.4f}")
        cmd = [ff, "-y", "-i", str(p), "-filter_complex", f"[0:v]setpts={1 / k:.5f}*PTS[v];[0:a]{','.join(at)}[a]", "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "veryfast", str(out)]
        if video_info(str(p))["ses"] == "yok":
            cmd = [ff, "-y", "-i", str(p), "-vf", f"setpts={1 / k:.5f}*PTS", "-c:v", "libx264", "-preset", "veryfast", str(out)]
    elif a == "resize":
        cmd = [ff, "-y", "-i", str(p), "-vf", f"scale={int(value or 1280)}:-2", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", str(out)]
    elif a == "mute":
        cmd = [ff, "-y", "-i", str(p), "-an", "-c:v", "copy", str(out)]
    elif a == "extract_audio":
        cmd = [ff, "-y", "-i", str(p), "-vn", "-q:a", "2", str(out)]
    elif a == "to_gif":
        cmd = [ff, "-y", *ss, *(["-t", str(_sec(end) - _sec(start or 0))] if end not in ("", None) else ["-t", "6"]), "-i", str(p), "-vf",
               "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", str(out)]
    elif a == "rotate":
        tr = {"90": "transpose=1", "-90": "transpose=2", "270": "transpose=2", "180": "transpose=1,transpose=1"}.get(str(value or "90"), "transpose=1")
        cmd = [ff, "-y", "-i", str(p), "-vf", tr, "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", str(out)]
    elif a == "compress":
        cmd = [ff, "-y", "-i", str(p), "-c:v", "libx264", "-preset", "veryfast", "-crf", str(int(value or 28)), "-c:a", "aac", "-b:a", "96k", str(out)]
    elif a == "subtitles":
        srt = _path(value)
        if not srt.exists():
            return f"Altyazı yok: {srt}"
        esc = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        cmd = [ff, "-y", "-i", str(p), "-vf", f"subtitles='{esc}':force_style='FontSize=22,Outline=2'", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", str(out)]
    elif a == "add_music":
        mus = _path(value)
        if not mus.exists():
            return f"Müzik yok: {mus}"
        cmd = [ff, "-y", "-i", str(p), "-stream_loop", "-1", "-i", str(mus), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)]
    elif a == "reverse":
        cmd = [ff, "-y", "-i", str(p), "-vf", "reverse", "-af", "areverse", "-c:v", "libx264", "-preset", "veryfast", str(out)]
        if video_info(str(p))["ses"] == "yok":
            cmd = [ff, "-y", "-i", str(p), "-vf", "reverse", "-c:v", "libx264", "-preset", "veryfast", str(out)]
    elif a == "thumbnail":
        cmd = [ff, "-y", "-ss", str(start or 1), "-i", str(p), "-frames:v", "1", str(out)]
    else:
        return "Bilinmeyen işlem. Seçenekler: cut, speed, resize, mute, extract_audio, to_gif, rotate, compress, subtitles, add_music, reverse, thumbnail"
    _run(cmd)
    res = {"çıktı": str(out), "boyut_MB": round(out.stat().st_size / 1e6, 2)}
    if out.suffix in (".mp4", ".webm", ".gif", ".jpg"):
        res.update({"ui": "image", "path": str(out), "title": f"{p.name} → {a}", "kind": "video" if out.suffix in (".mp4", ".webm") else "image"})
    return res


def _sec(t):
    if isinstance(t, (int, float)):
        return float(t)
    parts = [float(x) for x in str(t).replace(",", ".").split(":")]
    s = 0.0
    for x in parts:
        s = s * 60 + x
    return s


def video_merge(paths, output=""):
    files = [_path(x) for x in (paths if isinstance(paths, list) else str(paths).split(";"))]
    miss = [str(f) for f in files if not f.exists()]
    if miss:
        return f"Bulunamadı: {miss}"
    out = _path(output) if output else _out(f"birlesik_{time.strftime('%Y%m%d_%H%M%S')}.mp4", VOUT)
    ff = _ff()
    inputs, fil = [], ""
    for i, f in enumerate(files):
        inputs += ["-i", str(f)]
        fil += f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];"
    has_audio = all(video_info(str(f))["ses"] != "yok" for f in files)
    if has_audio:
        fil += "".join(f"[v{i}][{i}:a]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        fil += "".join(f"[v{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=0[v]"
        maps = ["-map", "[v]"]
    _run([ff, "-y", *inputs, "-filter_complex", fil, *maps, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", str(out)])
    return {"ui": "image", "path": str(out), "title": f"{len(files)} video birleştirildi", "kind": "video", "çıktı": str(out)}


def video_montage(images, music="", seconds=3, title="", output=""):
    """Resimlerden geçişli (yakınlaşma + solma) slayt videosu yapar; isteğe bağlı müzik ve başlık."""
    files = [_path(x) for x in (images if isinstance(images, list) else str(images).split(";"))]
    if len(files) == 1 and files[0].is_dir():
        files = sorted([f for f in files[0].iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")])
    files = [f for f in files if f.exists()]
    if not files:
        return "Resim bulunamadı."
    sec = float(seconds or 3)
    fps = 30
    ff = _ff()
    out = _path(output) if output else _out(f"montaj_{time.strftime('%Y%m%d_%H%M%S')}.mp4", VOUT)
    inputs, fil = [], ""
    for i, f in enumerate(files):
        inputs += ["-i", str(f)]  # tek kare; zoompan süreyi kendisi üretir (d kare)
        fil += (f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
                f"zoompan=z='min(zoom+0.0008,1.12)':d={int(sec * fps)}:s=1280x720:fps={fps},"
                f"fade=t=in:st=0:d=0.5,fade=t=out:st={sec - 0.5}:d=0.5,setsar=1[v{i}];")
    fil += "".join(f"[v{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=0[v0]"
    last = "[v0]"
    if title:
        fnt = next((x for x in ("C\\:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(x.replace("\\", ""))), "")
        ff_font = f"fontfile='{fnt}':" if fnt else ""
        safe = title.replace("'", "").replace(":", " ")
        fil += f";[v0]drawtext={ff_font}text='{safe}':fontsize=56:fontcolor=white:borderw=3:x=(w-tw)/2:y=h-120:enable='lt(t,{sec})'[v1]"
        last = "[v1]"
    cmd = [ff, "-y", *inputs]
    maps = ["-map", last]
    if music:
        m = _path(music)
        if m.exists():
            cmd += ["-i", str(m)]
            maps += ["-map", f"{len(files)}:a", "-shortest", "-c:a", "aac"]
    cmd += ["-filter_complex", fil, *maps, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)]
    _run(cmd, 1800)
    return {"ui": "image", "path": str(out), "title": title or f"Montaj ({len(files)} resim)", "kind": "video", "süre_sn": round(sec * len(files), 1)}


def studio_gallery(limit=24):
    items = []
    for folder in (OUT, VOUT):
        if folder.exists():
            items += [f for f in folder.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".svg")]
    items.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    items = [str(f) for f in items[:int(limit or 24)]]
    return {"ui": "gallery", "files": items, "title": "Stüdyo galerisi"} if items else "Galeri boş."


TOOLS = {
    "image_generate": (image_generate, _schema("Yapay zekâ ile metinden resim/görsel/illüstrasyon üretir ve ekranda gösterir (ücretsiz).",
                                               {"prompt": S("ne çizilsin (ayrıntılı, tercihen İngilizce)"), "style": S("stil: " + ", ".join(k for k in STYLES if k)),
                                                "width": {"type": "integer"}, "height": {"type": "integer"}, "seed": {"type": "integer"}, "count": {"type": "integer", "description": "1-4 varyant"}},
                                               ["prompt"]), False),
    "photo_edit": (photo_edit, _schema("Fotoğrafı düzenler (boyut, kırp, döndür, parlaklık, kontrast, filtre, yazı, filigran, arka plan sil, format). Orijinal korunur.",
                                       {"path": S("resim"), "operations": S(photo_edit.__doc__.split("İşlemler virgülle: ")[1]), "output": S("çıktı (boş: _duzenlendi)")},
                                       ["path", "operations"]), False),
    "photo_collage": (photo_collage, _schema("Birden çok resimden kolaj yapar.", {"paths": S("resim yolları ; ile"), "columns": {"type": "integer"}}, ["paths"]), False),
    "logo_make": (logo_make, _schema("Marka/şirket için vektör logo varyantları üretir (SVG + PNG).",
                                     {"name": S("marka adı"), "slogan": S("slogan"), "shape": S("daire/altıgen/kalkan/elmas/halka/kare"), "colors": S("#hex,#hex"),
                                      "count": {"type": "integer"}}, ["name"]), False),
    "video_info": (video_info, _schema("Video bilgisi: süre, çözünürlük, fps, kodek, ses.", {"path": S("video")}, ["path"]), False),
    "video_scenes": (video_scenes, _schema("Videodaki sahne değişimlerini bulur ve sahne küçük resimleri çıkarır.",
                                           {"path": S("video"), "threshold": {"type": "number", "description": "0.2 hassas – 0.5 kaba"}}, ["path"]), False),
    "video_analyze": (video_analyze, _schema("Videoyu izleyip analiz eder: kareler + konuşma → ne oluyor, kim/ne var, önemli anlar, özet.",
                                             {"path": S("video"), "question": S("soru"), "frames": {"type": "integer"}}, ["path"]), False),
    "video_edit": (video_edit, _schema("Video düzenler: cut, speed, resize, mute, extract_audio, to_gif, rotate, compress, subtitles, add_music, reverse, thumbnail.",
                                       {"path": S("video"), "action": S("işlem"), "start": S("başlangıç sn veya dd:ss"), "end": S("bitiş"), "value": S("değer/dosya"), "output": S("çıktı")},
                                       ["path", "action"]), False),
    "video_merge": (video_merge, _schema("Birden çok videoyu sırayla birleştirir.", {"paths": S("video yolları ; ile")}, ["paths"]), False),
    "video_montage": (video_montage, _schema("Resimlerden müzikli, geçişli slayt videosu (montaj) yapar.",
                                             {"images": S("resim yolları ; ile ya da klasör"), "music": S("müzik dosyası"), "seconds": {"type": "number"}, "title": S("başlık")},
                                             ["images"]), False),
    "studio_gallery": (studio_gallery, _schema("Üretilen resim ve videoların galerisini gösterir.", {"limit": {"type": "integer"}}), False),
}
