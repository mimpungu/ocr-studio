"""Serveur FastAPI pour OCR Studio."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import ocr_region, process_document
from .enhancer import anonymize_text
from .exporters import (
    export_csv,
    export_docx,
    export_edited_pdf,
    export_json,
    export_markdown,
    export_png,
    export_searchable_pdf,
    export_text,
)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="OCR Studio", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RegionRequest(BaseModel):
    image_data_url: str
    bbox: list[float]
    math: bool = False
    upscale: float = 2.0
    enhance: bool = True
    postprocess: bool = True


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ocr")
async def api_ocr(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    dpi: float = Form(200.0),
    furniture: bool = Form(False),
    math: bool = Form(False),
    enhance_scan: bool = Form(False),
    photo_mode: bool = Form(False),
    postprocess: bool = Form(True),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    filename = file.filename or "document.png"
    try:
        return process_document(
            file_bytes=data,
            filename=filename,
            mode=mode,
            dpi=dpi,
            furniture=furniture,
            math=math,
            enhance_scan=enhance_scan,
            photo_mode=photo_mode,
            postprocess=postprocess,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/anonymize")
def api_anonymize(doc_data: dict[str, Any]) -> dict[str, Any]:
    """Anonymise les emails, téléphones et IBAN dans tous les blocs du document."""
    for page in doc_data.get("pages", []):
        for blk in page.get("blocks", []):
            blk["text"] = anonymize_text(blk.get("text", ""))
        for ln in page.get("lines", []):
            ln["text"] = anonymize_text(ln.get("text", ""))
        page["text"] = anonymize_text(page.get("text", ""))
        page["markdown"] = anonymize_text(page.get("markdown", ""))
    return doc_data


@app.post("/api/ocr-region")
def api_ocr_region(req: RegionRequest) -> dict[str, Any]:
    try:
        return ocr_region(
            image_data_url=req.image_data_url,
            bbox=req.bbox,
            math=req.math,
            upscale=req.upscale,
            enhance=req.enhance,
            postprocess=req.postprocess,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export/{fmt}")
def api_export(fmt: str, doc_data: dict[str, Any]) -> Response:
    base_name = Path(doc_data.get("filename") or "document").stem
    fmt = fmt.lower()
    if fmt == "md":
        content = export_markdown(doc_data)
        media = "text/markdown; charset=utf-8"
        ext = "md"
    elif fmt == "txt":
        content = export_text(doc_data)
        media = "text/plain; charset=utf-8"
        ext = "txt"
    elif fmt == "csv":
        content = export_csv(doc_data)
        media = "text/csv; charset=utf-8"
        ext = "csv"
    elif fmt == "json":
        content = export_json(doc_data)
        media = "application/json; charset=utf-8"
        ext = "json"
    elif fmt == "docx":
        content = export_docx(doc_data)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = "docx"
    elif fmt == "pdf":
        content = export_searchable_pdf(doc_data)
        media = "application/pdf"
        ext = "pdf"
    elif fmt == "edited-pdf":
        content = export_edited_pdf(doc_data)
        media = "application/pdf"
        ext = "pdf"
    elif fmt == "png":
        content, media, ext = export_png(doc_data)
    else:
        raise HTTPException(status_code=400, detail=f"Format inconnu: {fmt}")

    safe_ascii = re.sub(r"[^A-Za-z0-9._-]", "_", base_name).strip("_") or "document"
    utf8_name = quote(f"{base_name}.{ext}")
    return Response(
        content=content,
        media_type=media,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_ascii}.{ext}"; filename*=UTF-8\'\'{utf8_name}'
            )
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Studio - Interface web OCR & édition")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    print(f"OCR Studio démarré sur http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
