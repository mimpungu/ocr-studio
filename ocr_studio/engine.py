"""Moteur OCR Studio basé sur indra-ocr avec prétraitement et post-traitement avancé."""

from __future__ import annotations

import base64
import io
import os
import re
import tempfile
import threading
import time
from typing import Any

import cv2
import indra_ocr
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from .enhancer import (
    clean_phone_photo,
    enhance_image_for_ocr,
    enhance_table_html,
    extract_entities,
    merge_cross_page_tables,
    postprocess_french_text,
)

_CONV_CACHE: dict[tuple[str, float, bool, bool], indra_ocr.Converter] = {}
_CACHE_LOCK = threading.Lock()


def get_converter(
    mode: str = "auto",
    dpi: float = 200.0,
    furniture: bool = False,
    math: bool = False,
) -> indra_ocr.Converter:
    """Retourne un Converter mis en cache pour éviter de recharger les modèles ONNX."""
    key = (mode, float(dpi), bool(furniture), bool(math))
    with _CACHE_LOCK:
        conv = _CONV_CACHE.get(key)
        if conv is None:
            threads = min(4, max(1, os.cpu_count() or 4))
            conv = indra_ocr.load(
                threads=threads,
                dpi=dpi,
                mode=mode,
                furniture=furniture,
                math=math,
            )
            _CONV_CACHE[key] = conv
        return conv


def _render_pdf_pages_png(pdf_bytes: bytes, dpi: float = 200.0) -> list[tuple[bytes, int, int]]:
    """Rend chaque page d'un PDF en PNG (bytes, width, height) à la résolution donnée."""
    doc = pdfium.PdfDocument(pdf_bytes)
    scale = dpi / 72.0
    out: list[tuple[bytes, int, int]] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            bitmap = page.render(scale=scale)
            pil_img = bitmap.to_pil()
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            out.append((buf.getvalue(), pil_img.width, pil_img.height))
    finally:
        doc.close()
    return out


def _render_image_pages_png(img_bytes: bytes, filename: str) -> list[tuple[bytes, int, int]]:
    """Convertit une image (y compris TIFF multi-pages) en liste de PNG (bytes, w, h)."""
    pil_img = Image.open(io.BytesIO(img_bytes))
    frames: list[tuple[bytes, int, int]] = []
    n_frames = getattr(pil_img, "n_frames", 1)
    for idx in range(n_frames):
        pil_img.seek(idx)
        rgb = pil_img.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        frames.append((buf.getvalue(), rgb.width, rgb.height))
    return frames


def _block_confidence(block_bbox: list[float], lines: list[Any]) -> float:
    """Calcule la confiance moyenne des lignes contenues dans un bloc."""
    bx0, by0, bx1, by1 = block_bbox
    confs = []
    for ln in lines:
        lx0, ly0, lx1, ly1 = ln.box
        cx = (lx0 + lx1) * 0.5
        cy = (ly0 + ly1) * 0.5
        if bx0 - 4 <= cx <= bx1 + 4 and by0 - 4 <= cy <= by1 + 4:
            confs.append(float(ln.conf))
    if not confs:
        return 1.0
    return round(sum(confs) / len(confs), 3)


def _blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Reconstruit un Markdown propre à partir des blocs (éventuellement améliorés)."""
    parts: list[str] = []
    for b in blocks:
        label = b.get("label", "Text")
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if label == "Section-Header":
            parts.append(f"## {text}")
        elif label == "Table":
            parts.append(text)
        else:
            parts.append(text)
    return "\n\n".join(parts)


def process_document(
    file_bytes: bytes,
    filename: str,
    mode: str = "auto",
    dpi: float = 200.0,
    furniture: bool = False,
    math: bool = False,
    enhance_scan: bool = False,
    photo_mode: bool = False,
    postprocess: bool = True,
) -> dict[str, Any]:
    """Traite un PDF ou une image et retourne une structure complète éditable."""
    t_start = time.perf_counter()
    is_pdf = filename.lower().endswith(".pdf")
    conv = get_converter(mode=mode, dpi=dpi, furniture=furniture, math=math)

    if is_pdf:
        rendered_pages = _render_pdf_pages_png(file_bytes, dpi=dpi)
    else:
        rendered_pages = _render_image_pages_png(file_bytes, filename)

    pages_raw: list[Any] = []
    if is_pdf and not enhance_scan and not photo_mode:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            pages_raw = [p for _, p in conv.convert(tmp_path)]
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    else:
        # Mode image ou prétraitement scan/photo activé
        for png_bytes, _, _ in rendered_pages:
            arr = np.frombuffer(png_bytes, dtype=np.uint8)
            gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            if photo_mode:
                gray = clean_phone_photo(gray)
            elif enhance_scan:
                gray = enhance_image_for_ocr(gray, upscale=1.0)
            pages_raw.append(conv.ocr(gray))

    # Construire les blocs enrichis page par page
    pages_blocks: list[list[dict[str, Any]]] = []
    pages_meta: list[dict[str, Any]] = []

    for idx, page in enumerate(pages_raw):
        png_bytes, img_w, img_h = rendered_pages[idx]
        b64_img = base64.b64encode(png_bytes).decode("ascii")

        lines_out = []
        for ln in page.lines:
            txt = postprocess_french_text(ln.text) if postprocess else ln.text
            lines_out.append(
                {
                    "box": [round(float(x), 1) for x in ln.box],
                    "text": txt,
                    "conf": round(float(ln.conf), 3),
                }
            )

        html_tables = re.findall(r"<table>.*?</table>", page.markdown or "", flags=re.DOTALL)
        table_cursor = 0
        blocks_out: list[dict[str, Any]] = []
        for b_idx, blk in enumerate(page.blocks):
            label = blk.get("label", "Text")
            bbox = [round(float(x), 1) for x in blk.get("bbox", [0, 0, 0, 0])]
            raw_text = blk.get("text", "")
            if label == "Table" and table_cursor < len(html_tables):
                raw_text = html_tables[table_cursor]
                table_cursor += 1

            if postprocess:
                if label == "Table":
                    clean_text = enhance_table_html(raw_text)
                else:
                    clean_text = postprocess_french_text(raw_text)
            else:
                clean_text = raw_text

            conf = _block_confidence(bbox, page.lines)
            blocks_out.append(
                {
                    "id": f"p{idx+1}_b{b_idx+1}",
                    "label": label,
                    "bbox": bbox,
                    "text": clean_text,
                    "conf": conf,
                }
            )

        confs = [l["conf"] for l in lines_out]
        pages_blocks.append(blocks_out)
        pages_meta.append(
            {
                "page_num": idx + 1,
                "width": img_w,
                "height": img_h,
                "image_data_url": f"data:image/png;base64,{b64_img}",
                "source": page.source,
                "rotation": page.rotation,
                "skew": page.skew,
                "vertical": page.vertical,
                "mean_conf": round(sum(confs) / len(confs), 3) if confs else 1.0,
                "min_conf": round(min(confs), 3) if confs else 1.0,
                "timings": page.timings,
                "lines": lines_out,
                "raw_markdown": page.markdown,
            }
        )

    # Fusion inter-pages des tableaux si activé
    if postprocess:
        pages_blocks = merge_cross_page_tables(pages_blocks)

    pages_out: list[dict[str, Any]] = []
    for meta, blks in zip(pages_meta, pages_blocks):
        md = _blocks_to_markdown(blks) if postprocess else meta["raw_markdown"]
        plain_text = "\n".join(l["text"] for l in meta["lines"])
        pages_out.append(
            {
                **{k: v for k, v in meta.items() if k != "raw_markdown"},
                "blocks": blks,
                "markdown": md,
                "text": plain_text,
            }
        )

    all_text = "\n".join(p["text"] for p in pages_out)
    entities = extract_entities(all_text)
    total_ms = round((time.perf_counter() - t_start) * 1000, 1)
    return {
        "filename": filename,
        "page_count": len(pages_out),
        "total_ms": total_ms,
        "entities": entities,
        "options": {
            "mode": mode,
            "dpi": dpi,
            "furniture": furniture,
            "math": math,
            "enhance_scan": enhance_scan,
            "photo_mode": photo_mode,
            "postprocess": postprocess,
        },
        "pages": pages_out,
    }


def ocr_region(
    image_data_url: str,
    bbox: list[float],
    math: bool = False,
    upscale: float = 2.0,
    enhance: bool = True,
    postprocess: bool = True,
) -> dict[str, Any]:
    """Relit une zone rectangulaire précise à haute résolution (re-OCR ciblé)."""
    header, b64 = image_data_url.split(",", 1) if "," in image_data_url else ("", image_data_url)
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError("Impossible de décoder l'image de la page.")

    h, w = gray.shape[:2]
    x0 = max(0, int(round(bbox[0])) - 6)
    y0 = max(0, int(round(bbox[1])) - 6)
    x1 = min(w, int(round(bbox[2])) + 6)
    y1 = min(h, int(round(bbox[3])) + 6)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Zone sélectionnée invalide.")

    crop = gray[y0:y1, x0:x1]
    if enhance:
        crop = enhance_image_for_ocr(crop, upscale=upscale)
    elif upscale > 1.01:
        crop = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)

    conv = get_converter(mode="ocr", dpi=200.0, furniture=True, math=math)
    page = conv.ocr(crop)

    lines = []
    for ln in page.lines:
        txt = postprocess_french_text(ln.text) if postprocess else ln.text
        lines.append({"text": txt, "conf": round(float(ln.conf), 3)})

    confs = [l["conf"] for l in lines]
    md = postprocess_french_text(page.markdown) if postprocess else page.markdown
    txt = "\n".join(l["text"] for l in lines)
    return {
        "text": txt,
        "markdown": md,
        "lines": lines,
        "mean_conf": round(sum(confs) / len(confs), 3) if confs else 0.0,
        "timings": page.timings,
    }
