"""Ofis işleri: Word, Excel, PowerPoint, PDF oluşturma/birleştirme/dönüştürme, grafik, veri analizi, karşılaştırma."""
import csv
import difflib
import io
import json
import re
import statistics
import subprocess
import sys
import time

from ..tools import N, S, _path, _schema, read_file

IS_WIN = sys.platform.startswith("win")


def _out(path, ext, default_name):
    p = _path(path) if path else _path("belgeler") / f"{default_name}_{time.strftime('%Y%m%d_%H%M')}{ext}"
    if p.suffix.lower() != ext:
        p = p.with_suffix(ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _rows(data):
    """JSON listesi, JSON nesne listesi ya da CSV/TSV metni → satırlar (ilk satır başlık)."""
    if isinstance(data, list):
        rows = data
    else:
        t = str(data).strip()
        try:
            rows = json.loads(t)
        except Exception:
            dialect = "\t" if "\t" in t.splitlines()[0] else (";" if t.splitlines()[0].count(";") > t.splitlines()[0].count(",") else ",")
            rows = list(csv.reader(io.StringIO(t), delimiter=dialect))
    if rows and isinstance(rows[0], dict):
        keys = list(rows[0].keys())
        rows = [keys] + [[r.get(k, "") for k in keys] for r in rows]
    out = []
    for r in rows:
        conv = []
        for v in r:
            if isinstance(v, str):
                vs = v.strip().replace(" ", "")
                if re.fullmatch(r"-?\d+", vs):
                    v = int(vs)
                elif re.fullmatch(r"-?\d+[.,]\d+", vs):
                    v = float(vs.replace(",", "."))
            conv.append(v)
        out.append(conv)
    return out


# ===================== Word =====================
def create_word(title, content, path=""):
    """content: '# Başlık', '## Alt başlık', '- madde', '1. madde', '**kalın**', boş satır = paragraf."""
    try:
        import docx
        from docx.shared import Pt
    except ImportError:
        return "python-docx gerekli (requirements-extra.txt)."
    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    d.add_heading(title, 0)
    tbl = None
    for line in str(content).splitlines():
        s = line.rstrip()
        is_row = s.startswith("|") and s.endswith("|") and len(s) > 1
        if not is_row:
            tbl = None
        if not s.strip():
            continue
        if is_row:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c) for c in cells):
                continue
            if tbl is None:
                tbl = d.add_table(rows=0, cols=len(cells))
                tbl.style = "Table Grid"
                head = True
            else:
                head = False
            row = tbl.add_row().cells
            for i, c in enumerate(cells[: len(row)]):
                row[i].text = c
                if head:
                    for r in row[i].paragraphs[0].runs:
                        r.bold = True
        elif s.startswith("### "):
            d.add_heading(s[4:], 3)
        elif s.startswith("## "):
            d.add_heading(s[3:], 2)
        elif s.startswith("# "):
            d.add_heading(s[2:], 1)
        elif re.match(r"^\s*[-*•] ", s):
            _runs(d.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*•] ", "", s))
        elif re.match(r"^\s*\d+[.)] ", s):
            _runs(d.add_paragraph(style="List Number"), re.sub(r"^\s*\d+[.)] ", "", s))
        else:
            _runs(d.add_paragraph(), s)
    p = _out(path, ".docx", re.sub(r"\W+", "_", title)[:40] or "belge")
    d.save(p)
    return f"Word belgesi oluşturuldu: {p}"


def _runs(par, text):
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        r = par.add_run(part)
        r.bold = i % 2 == 1



# ===================== Excel =====================
def create_excel(data, path="", sheet="Sayfa1", chart="", chart_title=""):
    """data: CSV metni veya JSON satırları; ilk satır başlık. chart: bar | line | pie (ilk sütun etiket, ikinci değer)."""
    try:
        import openpyxl
        from openpyxl.chart import BarChart, LineChart, PieChart, Reference
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return "openpyxl gerekli."
    rows = _rows(data)
    if not rows:
        return "Veri boş."
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet[:30]
    for r in rows:
        ws.append(r)
    head = PatternFill("solid", fgColor="1F4E78")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head
        c.alignment = Alignment(horizontal="center")
    for i, col in enumerate(zip(*rows), 1):
        ws.column_dimensions[get_column_letter(i)].width = min(50, max(10, max(len(str(v)) for v in col) + 2))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    # sayısal sütunlara toplam satırı
    n = len(rows)
    numeric = [i for i in range(len(rows[0])) if all(isinstance(r[i], (int, float)) for r in rows[1:] if i < len(r) and r[i] != "")]
    if n > 2 and numeric:
        ws.cell(row=n + 1, column=1, value="TOPLAM").font = Font(bold=True)
        for i in numeric:
            if i == 0:
                continue
            L = get_column_letter(i + 1)
            c = ws.cell(row=n + 1, column=i + 1, value=f"=SUM({L}2:{L}{n})")
            c.font = Font(bold=True)
    if chart and n > 1 and len(rows[0]) > 1:
        ch = {"line": LineChart, "pie": PieChart}.get(chart, BarChart)()
        ch.title = chart_title or rows[0][1]
        vals = Reference(ws, min_col=2, max_col=min(len(rows[0]), 2 if chart == "pie" else len(rows[0])), min_row=1, max_row=n)
        cats = Reference(ws, min_col=1, min_row=2, max_row=n)
        ch.add_data(vals, titles_from_data=True)
        ch.set_categories(cats)
        ch.width, ch.height = 18, 9
        ws.add_chart(ch, f"{get_column_letter(len(rows[0]) + 2)}2")
    p = _out(path, ".xlsx", "tablo")
    wb.save(p)
    return f"Excel dosyası oluşturuldu: {p} ({n - 1} satır)"


def edit_excel(path, cell, value, sheet=""):
    import openpyxl
    p = _path(path)
    wb = openpyxl.load_workbook(p)
    ws = wb[sheet] if sheet else wb.active
    ws[cell] = value
    wb.save(p)
    return f"{p.name}: {cell} = {value}"


# ===================== PowerPoint =====================
def create_powerpoint(title, slides, path="", subtitle=""):
    """slides: JSON [{"title": "...", "bullets": ["...", "..."], "notes": "..."}] veya
    düz metin: her '# Başlık' yeni slayt, altındaki '- ' satırları maddeler."""
    try:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.util import Inches, Pt
    except ImportError:
        return "python-pptx gerekli."
    if isinstance(slides, str):
        try:
            slides = json.loads(slides)
        except Exception:
            parsed, cur = [], None
            for line in slides.splitlines():
                s = line.strip()
                if s.startswith("#"):
                    cur = {"title": s.lstrip("# "), "bullets": []}
                    parsed.append(cur)
                elif s and cur is not None:
                    cur["bullets"].append(re.sub(r"^[-*•]\s*", "", s))
            slides = parsed
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    bg, fg, accent = RGBColor(0x0B, 0x16, 0x22), RGBColor(0xEE, 0xF4, 0xF8), RGBColor(0x38, 0xD6, 0xFF)

    def paint(sl):
        f = sl.background.fill
        f.solid()
        f.fore_color.rgb = bg

    s0 = prs.slides.add_slide(prs.slide_layouts[0])
    paint(s0)
    s0.shapes.title.text = title
    s0.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = accent
    s0.shapes.title.text_frame.paragraphs[0].runs[0].font.bold = True
    if len(s0.placeholders) > 1:
        s0.placeholders[1].text = subtitle or time.strftime("%d.%m.%Y")
        s0.placeholders[1].text_frame.paragraphs[0].runs[0].font.color.rgb = fg
    for sd in slides:
        sl = prs.slides.add_slide(prs.slide_layouts[1])
        paint(sl)
        sl.shapes.title.text = sd.get("title", "")
        for r in sl.shapes.title.text_frame.paragraphs[0].runs:
            r.font.color.rgb = accent
            r.font.bold = True
        body = sl.placeholders[1]
        body.left, body.top, body.width, body.height = Inches(0.8), Inches(1.6), Inches(11.7), Inches(5.4)
        tf = body.text_frame
        tf.clear()
        for i, b in enumerate(sd.get("bullets", [])):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = str(b)
            for r in para.runs:
                r.font.size = Pt(24)
                r.font.color.rgb = fg
        if sd.get("notes"):
            sl.notes_slide.notes_text_frame.text = sd["notes"]
    p = _out(path, ".pptx", re.sub(r"\W+", "_", title)[:40] or "sunum")
    prs.save(p)
    return f"PowerPoint sunumu oluşturuldu: {p} ({len(slides) + 1} slayt)"


# ===================== PDF =====================
def create_pdf(title, content, path=""):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import ListFlowable, Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        # reportlab yoksa Word üzerinden dene
        w = create_word(title, content, str(_out(path, ".docx", "belge")))
        return w + " (PDF için reportlab kurulu değil; convert_to_pdf ile çevirebilirsin)"
    font = "Helvetica"
    for cand in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            pdfmetrics.registerFont(TTFont("TRFont", cand))
            font = "TRFont"
            break
        except Exception:
            pass
    ss = getSampleStyleSheet()
    for k in ("Title", "Heading1", "Heading2", "BodyText"):
        ss[k].fontName = font
    story = [Paragraph(title, ss["Title"]), Spacer(1, 12)]
    bullets = []

    def flush():
        if bullets:
            story.append(ListFlowable([Paragraph(b, ss["BodyText"]) for b in bullets], bulletType="bullet"))
            bullets.clear()
    for line in str(content).splitlines():
        s = line.strip()
        s_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s.replace("&", "&amp;").replace("<", "&lt;"))
        if not s:
            flush()
            continue
        if s.startswith("## "):
            flush()
            story.append(Paragraph(s_html[3:], ss["Heading2"]))
        elif s.startswith("# "):
            flush()
            story.append(Paragraph(s_html[2:], ss["Heading1"]))
        elif re.match(r"^[-*•] ", s):
            bullets.append(s_html[2:])
        else:
            flush()
            story.append(Paragraph(s_html, ss["BodyText"]))
    flush()
    p = _out(path, ".pdf", re.sub(r"\W+", "_", title)[:40] or "belge")
    SimpleDocTemplate(str(p), pagesize=A4, title=title).build(story)
    return f"PDF oluşturuldu: {p}"


def merge_pdfs(paths, output=""):
    from pypdf import PdfWriter
    w = PdfWriter()
    files = [_path(x.strip()) for x in str(paths).split(",") if x.strip()]
    for f in files:
        w.append(str(f))
    p = _out(output, ".pdf", "birlesik")
    with open(p, "wb") as fh:
        w.write(fh)
    return f"{len(files)} PDF birleştirildi: {p}"


def split_pdf(path, pages, output=""):
    """pages: '1-3,5' gibi."""
    from pypdf import PdfReader, PdfWriter
    r = PdfReader(str(_path(path)))
    w = PdfWriter()
    for part in str(pages).split(","):
        a, _, b = part.strip().partition("-")
        for i in range(int(a), int(b or a) + 1):
            if 1 <= i <= len(r.pages):
                w.add_page(r.pages[i - 1])
    p = _out(output, ".pdf", "sayfalar")
    with open(p, "wb") as fh:
        w.write(fh)
    return f"{len(w.pages)} sayfa kaydedildi: {p}"


def convert_to_pdf(path):
    """Word/Excel/PowerPoint dosyasını PDF'e çevirir (bilgisayarda Office kurulu olmalı)."""
    src = _path(path)
    if not src.exists():
        return f"Bulunamadı: {src}"
    out = src.with_suffix(".pdf")
    if not IS_WIN:
        r = subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(src.parent), str(src)], capture_output=True)
        return f"PDF: {out}" if out.exists() else "Dönüştürülemedi (LibreOffice gerekli)."
    ext = src.suffix.lower()
    s, o = str(src).replace("'", "''"), str(out).replace("'", "''")
    if ext in (".doc", ".docx", ".rtf", ".txt"):
        cmd = f"$w=New-Object -ComObject Word.Application; $d=$w.Documents.Open('{s}'); $d.SaveAs([ref]'{o}',[ref]17); $d.Close(); $w.Quit()"
    elif ext in (".xls", ".xlsx"):
        cmd = f"$x=New-Object -ComObject Excel.Application; $b=$x.Workbooks.Open('{s}'); $b.ExportAsFixedFormat(0,'{o}'); $b.Close($false); $x.Quit()"
    elif ext in (".ppt", ".pptx"):
        cmd = f"$p=New-Object -ComObject PowerPoint.Application; $d=$p.Presentations.Open('{s}',$true,$false,$false); $d.SaveAs('{o}',32); $d.Close(); $p.Quit()"
    else:
        return "Desteklenmeyen tür."
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=120)
    return f"PDF oluşturuldu: {out}" if out.exists() else "Dönüştürülemedi (Microsoft Office kurulu olmalı)."


# ===================== analiz / grafik / karşılaştırma =====================
def _load_table(path):
    p = _path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        ws = openpyxl.load_workbook(p, read_only=True, data_only=True).active
        return [list(r) for r in ws.iter_rows(values_only=True) if any(v is not None for v in r)]
    return _rows(p.read_text(encoding="utf-8", errors="ignore"))


def analyze_data(path):
    rows = _load_table(path)
    if len(rows) < 2:
        return "Veri yok."
    head, body = rows[0], rows[1:]
    rep = {"satır": len(body), "sütunlar": head, "sütun_özeti": {}}
    for i, h in enumerate(head):
        col = [r[i] for r in body if i < len(r) and r[i] not in (None, "")]
        nums = [float(v) for v in col if isinstance(v, (int, float))]
        if nums and len(nums) >= len(col) * 0.8:
            rep["sütun_özeti"][str(h)] = {"toplam": round(sum(nums), 2), "ortalama": round(statistics.mean(nums), 2),
                                         "min": min(nums), "max": max(nums),
                                         "medyan": round(statistics.median(nums), 2)}
        else:
            freq = {}
            for v in col:
                freq[str(v)] = freq.get(str(v), 0) + 1
            rep["sütun_özeti"][str(h)] = {"farklı_değer": len(freq),
                                         "en_sık": sorted(freq.items(), key=lambda x: -x[1])[:5]}
    rep["ilk_satırlar"] = body[:5]
    return rep


def make_chart(data, kind="bar", title="", path=""):
    """data: CSV/JSON (ilk sütun etiket, diğerleri seri) ya da .csv/.xlsx dosya yolu. PNG kaydeder."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = _load_table(data) if _path(str(data)).suffix.lower() in (".csv", ".xlsx", ".tsv") and _path(str(data)).exists() else _rows(data)
    head, body = rows[0], rows[1:]
    labels = [str(r[0]) for r in body]
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=120)
    if kind == "pie":
        ax.pie([float(r[1]) for r in body], labels=labels, autopct="%1.0f%%")
    else:
        n = len(head) - 1
        for j in range(1, len(head)):
            vals = [float(r[j]) if isinstance(r[j], (int, float)) else 0 for r in body]
            if kind == "line":
                ax.plot(labels, vals, marker="o", label=str(head[j]))
            else:
                w = 0.8 / n
                ax.bar([i + (j - 1) * w - 0.4 + w / 2 for i in range(len(labels))], vals, width=w, label=str(head[j]))
                ax.set_xticks(range(len(labels)), labels)
        if n > 1:
            ax.legend()
        ax.grid(axis="y", alpha=0.3)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    ax.set_title(title or str(head[1] if len(head) > 1 else ""))
    plt.xticks(rotation=30 if len(labels) > 6 else 0)
    plt.tight_layout()
    p = _out(path, ".png", "grafik")
    fig.savefig(p)
    plt.close(fig)
    return f"Grafik kaydedildi: {p}"


def compare_files(path_a, path_b):
    a = read_file(path_a, 200000).splitlines()
    b = read_file(path_b, 200000).splitlines()
    diff = list(difflib.unified_diff(a, b, "A", "B", lineterm="", n=1))
    ratio = difflib.SequenceMatcher(None, "\n".join(a), "\n".join(b)).ratio()
    return {"benzerlik_%": round(ratio * 100, 1), "farklar": "\n".join(diff[:200]) or "Aynı."}


def _money(x, cur):
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {cur}"


def invoice_create(customer, items, tax_rate=20, currency="TL", seller="", invoice_no="", due_days=30, note="", path=""):
    """Fatura/proforma PDF: kalemler 'ad;adet;birim fiyat' satırları ('|' ya da yeni satırla ayrılmış). KDV oranı %, ara toplam/KDV/genel toplam hesaplanır.
    Satıcı bilgisi verilmezse hafızadaki 'fatura satıcı' bilgisi ya da boş bırakılır. (Resmî e-Fatura değildir; GİB e-Fatura için entegratör gerekir.)"""
    from datetime import date, timedelta
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return "Fatura PDF'i için reportlab gerekli (pip install reportlab)."
    rows = []
    for ln in re.split(r"[|\n]", str(items)):
        parts = [x.strip() for x in ln.split(";")]
        if len(parts) < 3 or not parts[0]:
            continue
        try:
            q = float(parts[1].replace(",", "."))
            pr = float(parts[2].replace(".", "").replace(",", ".")) if parts[2].count(",") == 1 and parts[2].count(".") >= 1 else float(parts[2].replace(",", "."))
        except ValueError:
            return f"Kalem okunamadı: '{ln}'. Biçim: ad;adet;birim fiyat"
        rows.append((parts[0], q, pr, round(q * pr, 2)))
    if not rows:
        return "Kalem yok. Biçim: 'Web tasarımı;1;15000 | Hosting;12;250'"
    sub = round(sum(r[3] for r in rows), 2)
    tax = round(sub * float(tax_rate) / 100, 2)
    total = round(sub + tax, 2)
    no = invoice_no or time.strftime("F%Y%m%d-%H%M")
    today = date.today()
    font, bold = "Helvetica", "Helvetica-Bold"
    for reg, bd in (("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"), ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
        try:
            pdfmetrics.registerFont(TTFont("TRF", reg))
            pdfmetrics.registerFont(TTFont("TRFB", bd))
            font, bold = "TRF", "TRFB"
            break
        except Exception:
            pass
    ss = getSampleStyleSheet()
    for k in ("Title", "Normal", "BodyText"):
        ss[k].fontName = font
    ss["Title"].fontName = bold
    esc = lambda t: str(t).replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br/>")  # noqa: E731
    story = [Paragraph("FATURA", ss["Title"]),
             Table([[Paragraph(f"<b>Satıcı</b><br/>{esc(seller or '—')}", ss["Normal"]), Paragraph(f"<b>Fatura no:</b> {esc(no)}<br/><b>Tarih:</b> {today:%d.%m.%Y}<br/>"
                                                                                             f"<b>Son ödeme:</b> {today + timedelta(days=int(due_days)):%d.%m.%Y}", ss["Normal"])],
                    [Paragraph(f"<b>Alıcı</b><br/>{esc(customer)}", ss["Normal"]), ""]], colWidths=[300, 200]),
             Spacer(1, 14)]
    data = [["#", "Açıklama", "Adet", "Birim fiyat", "Tutar"]] + [[str(i + 1), Paragraph(esc(r[0]), ss["Normal"]), f"{r[1]:g}", _money(r[2], currency), _money(r[3], currency)] for i, r in enumerate(rows)]
    data += [["", "", "", "Ara toplam", _money(sub, currency)], ["", "", "", f"KDV %{float(tax_rate):g}", _money(tax, currency)], ["", "", "", "GENEL TOPLAM", _money(total, currency)]]
    t = Table(data, colWidths=[24, 236, 50, 95, 95])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("FONTNAME", (0, 0), (-1, 0), bold), ("FONTNAME", (3, -1), (-1, -1), bold),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a6cff")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -4), 0.25, colors.grey), ("LINEABOVE", (3, -3), (-1, -3), 0.8, colors.black),
                           ("BACKGROUND", (3, -1), (-1, -1), colors.HexColor("#e8f1ff")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 18)]
    if note:
        story.append(Paragraph(esc(note), ss["Normal"]))
    story.append(Paragraph("<font size=8 color='#777777'>Bu belge bilgi amaçlı fatura/proforma örneğidir; resmî e-Fatura/e-Arşiv yerine geçmez.</font>", ss["Normal"]))
    p = _out(path, ".pdf", f"fatura_{re.sub(r'[^\w]+', '_', str(customer))[:20]}")
    SimpleDocTemplate(str(p), pagesize=A4, title=f"Fatura {no}").build(story)
    return {"fatura": str(p), "no": no, "kalem": len(rows), "ara_toplam": sub, "kdv": tax, "genel_toplam": total, "para": currency}


TOOLS = {
    "invoice_create": (invoice_create, _schema("Fatura/proforma PDF'i hazırlar (kalemler, KDV, toplamlar).",
                                               {"customer": S("alıcı adı/adresi"), "items": S("ad;adet;birim fiyat | ad;adet;fiyat"), "tax_rate": {"type": "number"}, "currency": S("TL/USD/EUR"),
                                                "seller": S("satıcı bilgisi"), "invoice_no": S("fatura no"), "due_days": {"type": "integer"}, "note": S("not")}, ["customer", "items"]), False),
    "create_word": (create_word, _schema("Word (.docx) belgesi oluşturur. content'te '# başlık', '- madde', '**kalın**', '| tablo |' kullanılabilir.",
                                         {"title": S("başlık"), "content": S("içerik"), "path": S("kayıt yolu (boşsa Belgeler)")}, ["title", "content"]), False),
    "create_excel": (create_excel, _schema("Excel tablosu oluşturur (başlık biçimi, filtre, toplam satırı, isteğe bağlı grafik).",
                                           {"data": S("CSV metni veya JSON satırlar; ilk satır başlık"), "path": S("yol"),
                                            "sheet": S("sayfa adı"), "chart": {"type": "string", "enum": ["bar", "line", "pie"], "description": "İsteğe bağlı; grafik istenmiyorsa bu parametreyi gönderme."},
                                            "chart_title": S("grafik başlığı")}, ["data"]), False),
    "edit_excel": (edit_excel, _schema("Excel hücresine değer/formül yazar.", {"path": S("dosya"), "cell": S("örn B3"),
                                       "value": S("değer veya =FORMÜL"), "sheet": S("sayfa")}, ["path", "cell", "value"]), True),
    "create_powerpoint": (create_powerpoint, _schema("PowerPoint sunumu oluşturur (koyu tema).",
                                                     {"title": S("sunum başlığı"), "subtitle": S("alt başlık"),
                                                      "slides": S("JSON [{title, bullets[], notes}] veya '# Slayt' + '- madde' metni"),
                                                      "path": S("yol")}, ["title", "slides"]), False),
    "create_pdf": (create_pdf, _schema("PDF belge/rapor oluşturur.", {"title": S("başlık"), "content": S("içerik"), "path": S("yol")}, ["title", "content"]), False),
    "merge_pdfs": (merge_pdfs, _schema("PDF'leri birleştirir.", {"paths": S("dosyalar, virgülle, sırayla"), "output": S("çıktı")}, ["paths"]), False),
    "split_pdf": (split_pdf, _schema("PDF'ten sayfa ayırır.", {"path": S("pdf"), "pages": S("örn 1-3,7"), "output": S("çıktı")}, ["path", "pages"]), False),
    "convert_to_pdf": (convert_to_pdf, _schema("Word/Excel/PowerPoint dosyasını PDF'e çevirir.", {"path": S("dosya")}, ["path"]), False),
    "analyze_data": (analyze_data, _schema("CSV/Excel verisini analiz eder (toplam, ortalama, en sık değerler).", {"path": S("dosya")}, ["path"]), False),
    "make_chart": (make_chart, _schema("Veriden grafik (PNG) çizer.", {"data": S("CSV/JSON veya dosya yolu"),
                                       "kind": {"type": "string", "enum": ["bar", "line", "pie"]}, "title": S("başlık"), "path": S("yol")}, ["data"]), False),
    "compare_files": (compare_files, _schema("İki dosyayı karşılaştırır.", {"path_a": S("dosya A"), "path_b": S("dosya B")}, ["path_a", "path_b"]), False),
}
