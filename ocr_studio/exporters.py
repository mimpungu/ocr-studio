"""Exportateurs multi-formats depuis le document édité (MD, TXT, DOCX, CSV, JSON, PDF searchable)."""

from __future__ import annotations

import base64
import csv
import html
import io
import json
import os
import re
import zipfile
from typing import Any

import docx
import pypdfium2 as pdfium
from docx.shared import Pt
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .enhancer import parse_html_table

_PDF_FONT_REGISTERED = False


def _get_pdf_font_name() -> str:
    """Enregistre une police Unicode (Arial/DejaVu) si disponible pour les accents et symboles."""
    global _PDF_FONT_REGISTERED
    if _PDF_FONT_REGISTERED:
        return "OCRStudioSans"
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path) and path.endswith(".ttf"):
            try:
                pdfmetrics.registerFont(TTFont("OCRStudioSans", path))
                _PDF_FONT_REGISTERED = True
                return "OCRStudioSans"
            except Exception:
                pass
    return "Helvetica"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip()


def export_markdown(doc_data: dict[str, Any]) -> bytes:
    """Exporte le document complet en Markdown."""
    sections: list[str] = []
    for page in doc_data.get("pages", []):
        parts: list[str] = []
        for blk in page.get("blocks", []):
            label = blk.get("label", "Text")
            txt = (blk.get("text") or "").strip()
            if not txt:
                continue
            if label == "Section-Header":
                parts.append(f"## {txt}")
            else:
                parts.append(txt)
        if parts:
            sections.append("\n\n".join(parts))
    return "\n\n---\n\n".join(sections).encode("utf-8")


def export_text(doc_data: dict[str, Any]) -> bytes:
    """Exporte le document en texte brut."""
    pages_txt: list[str] = []
    for page in doc_data.get("pages", []):
        parts: list[str] = []
        for blk in page.get("blocks", []):
            label = blk.get("label", "Text")
            txt = (blk.get("text") or "").strip()
            if not txt:
                continue
            if label == "Table":
                rows = parse_html_table(txt)
                for _, cells in rows:
                    parts.append(" | ".join(cells))
            else:
                parts.append(txt)
        pages_txt.append("\n\n".join(parts))
    return "\n\n".join(pages_txt).encode("utf-8")


def export_csv(doc_data: dict[str, Any]) -> bytes:
    """Exporte tous les tableaux du document en CSV (UTF-8 avec BOM pour Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    table_idx = 0
    for p_idx, page in enumerate(doc_data.get("pages", []), 1):
        for blk in page.get("blocks", []):
            if blk.get("label") != "Table":
                continue
            rows = parse_html_table(blk.get("text", ""))
            if not rows:
                continue
            table_idx += 1
            if table_idx > 1:
                writer.writerow([])
            writer.writerow([f"# Tableau {table_idx} (Page {p_idx})"])
            for _, cells in rows:
                writer.writerow(cells)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def export_json(doc_data: dict[str, Any]) -> bytes:
    """Exporte les données structurées (sans les images base64 lourdes)."""
    clean_pages = []
    for p in doc_data.get("pages", []):
        clean_p = {k: v for k, v in p.items() if k != "image_data_url"}
        clean_pages.append(clean_p)
    payload = {
        "filename": doc_data.get("filename"),
        "page_count": doc_data.get("page_count"),
        "options": doc_data.get("options"),
        "pages": clean_pages,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_docx(doc_data: dict[str, Any]) -> bytes:
    """Exporte le document édité en vrai fichier Word (.docx) avec titres et tableaux."""
    word_doc = docx.Document()
    style = word_doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    pages = doc_data.get("pages", [])
    for p_idx, page in enumerate(pages):
        if p_idx > 0:
            word_doc.add_page_break()
        for blk in page.get("blocks", []):
            label = blk.get("label", "Text")
            txt = (blk.get("text") or "").strip()
            if not txt:
                continue
            if label == "Section-Header":
                word_doc.add_heading(txt, level=2)
            elif label == "Table":
                rows = parse_html_table(txt)
                if rows:
                    ncols = max(len(r[1]) for r in rows)
                    tbl = word_doc.add_table(rows=len(rows), cols=ncols)
                    tbl.style = "Table Grid"
                    for r_i, (is_th, cells) in enumerate(rows):
                        for c_i in range(ncols):
                            val = cells[c_i] if c_i < len(cells) else ""
                            cell = tbl.cell(r_i, c_i)
                            cell.text = val
                            if is_th and cell.paragraphs and cell.paragraphs[0].runs:
                                cell.paragraphs[0].runs[0].bold = True
                    word_doc.add_paragraph("")
            elif label == "List-Group":
                for line in txt.splitlines():
                    line_c = line.strip().lstrip("•-* ").strip()
                    if line_c:
                        word_doc.add_paragraph(line_c, style="List Bullet")
            else:
                word_doc.add_paragraph(txt)

    buf = io.BytesIO()
    word_doc.save(buf)
    return buf.getvalue()


def export_searchable_pdf(doc_data: dict[str, Any]) -> bytes:
    """Génère un PDF avec l'image de chaque page et la couche texte éditée (sélectionnable)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    font_name = _get_pdf_font_name()

    for page in doc_data.get("pages", []):
        data_url = page.get("image_data_url", "")
        if not data_url:
            continue
        _, b64 = data_url.split(",", 1) if "," in data_url else ("", data_url)
        img_bytes = base64.b64decode(b64)
        pil_img = Image.open(io.BytesIO(img_bytes))
        w_px, h_px = pil_img.size

        # Conversion pixels -> points PDF (72 dpi base)
        dpi = float(doc_data.get("options", {}).get("dpi", 200.0) or 200.0)
        scale = 72.0 / dpi
        w_pt = w_px * scale
        h_pt = h_px * scale
        c.setPageSize((w_pt, h_pt))

        # Dessiner l'image en fond
        c.drawImage(ImageReader(pil_img), 0, 0, width=w_pt, height=h_pt)

        # Couche texte invisible basée sur les BLOCS ÉDITÉS (render mode 3 = invisible)
        blocks = page.get("blocks") or []
        if blocks:
            for blk in blocks:
                label = blk.get("label", "Text")
                raw_txt = (blk.get("text") or "").strip()
                if not raw_txt:
                    continue
                if label == "Table" and "<table" in raw_txt:
                    rows = parse_html_table(raw_txt)
                    lines_txt = [" | ".join(cells) for _, cells in rows if any(cells)]
                else:
                    lines_txt = [l.strip() for l in raw_txt.splitlines() if l.strip()]
                if not lines_txt:
                    continue

                box = blk.get("bbox")
                if box and len(box) == 4 and box[2] > box[0] and box[3] > box[1]:
                    x0, y0, x1, y1 = box
                else:
                    # Bloc ajouté manuellement sans bbox : placé en bas de page
                    x0, y0, x1, y1 = 20.0, h_px - 40.0, w_px - 20.0, h_px - 10.0

                x_pt = x0 * scale
                box_h_pt = (y1 - y0) * scale
                line_step_pt = max(8.0, box_h_pt / max(1, len(lines_txt)))
                font_sz = max(6.0, min(14.0, line_step_pt * 0.78))

                for idx, line_str in enumerate(lines_txt):
                    y_pt = h_pt - (y0 * scale) - ((idx + 0.85) * line_step_pt)
                    y_pt = max(4.0, min(h_pt - 4.0, y_pt))
                    text_obj = c.beginText(x_pt, y_pt)
                    text_obj.setTextRenderMode(3)
                    text_obj.setFont(font_name, font_sz)
                    text_obj.textOut(line_str)
                    c.drawText(text_obj)
        else:
            for ln in page.get("lines", []):
                txt = (ln.get("text") or "").strip()
                box = ln.get("box")
                if not txt or not box or len(box) != 4:
                    continue
                x0, y0, x1, y1 = box
                x_pt = x0 * scale
                y_pt = h_pt - (y1 * scale)
                box_h_pt = max(6.0, (y1 - y0) * scale * 0.85)
                text_obj = c.beginText(x_pt, y_pt)
                text_obj.setTextRenderMode(3)
                text_obj.setFont(font_name, box_h_pt)
                text_obj.textOut(txt)
                c.drawText(text_obj)

        c.showPage()

    c.save()
    return buf.getvalue()


def export_edited_pdf(doc_data: dict[str, Any]) -> bytes:
    """Génère un PDF visuellement recomposé avec tout le texte et les tableaux édités."""
    buf = io.BytesIO()
    font_name = _get_pdf_font_name()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=48,
        bottomMargin=48,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "OCRBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10.5,
        leading=14.5,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "OCRHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13.5,
        leading=17,
        spaceBefore=10,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "OCRCell",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9.5,
        leading=12.5,
    )

    story: list[Any] = []
    pages = doc_data.get("pages", [])
    for p_idx, page in enumerate(pages):
        if p_idx > 0:
            story.append(PageBreak())
        for blk in page.get("blocks", []):
            label = blk.get("label", "Text")
            txt = (blk.get("text") or "").strip()
            if not txt:
                continue
            if label == "Section-Header":
                story.append(Paragraph(html.escape(txt).replace("\n", "<br/>"), heading_style))
            elif label == "Table" and "<table" in txt:
                rows = parse_html_table(txt)
                if rows:
                    ncols = max(len(r[1]) for r in rows)
                    tbl_data = []
                    for _, cells in rows:
                        row_cells = [
                            Paragraph(html.escape(cells[c_i] if c_i < len(cells) else ""), cell_style)
                            for c_i in range(ncols)
                        ]
                        tbl_data.append(row_cells)
                    col_w = (A4[0] - 96) / max(1, ncols)
                    tbl = Table(tbl_data, colWidths=[col_w] * ncols, repeatRows=1)
                    tbl.setStyle(
                        TableStyle(
                            [
                                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f8")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ]
                        )
                    )
                    story.append(tbl)
                    story.append(Spacer(1, 8))
            else:
                safe = html.escape(txt).replace("\n", "<br/>")
                story.append(Paragraph(safe, body_style))

    if not story:
        story.append(Paragraph("(Document vide)", body_style))
    pdf.build(story)
    return buf.getvalue()


def export_png(doc_data: dict[str, Any]) -> tuple[bytes, str, str]:
    """Exporte le document édité en image PNG (ou ZIP de PNG si multi-pages).

    Retourne (bytes, media_type, extension).
    """
    pdf_bytes = export_edited_pdf(doc_data)
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    scale = 200.0 / 72.0
    try:
        if len(pdf_doc) == 1:
            pil_img = pdf_doc[0].render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            return buf.getvalue(), "image/png", "png"

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i in range(len(pdf_doc)):
                pil_img = pdf_doc[i].render(scale=scale).to_pil()
                img_buf = io.BytesIO()
                pil_img.save(img_buf, format="PNG")
                zf.writestr(f"page_{i + 1}.png", img_buf.getvalue())
        return zip_buf.getvalue(), "application/zip", "zip"
    finally:
        pdf_doc.close()
