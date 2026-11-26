import difflib
import numpy as np
from fastapi.testclient import TestClient

from ocr_studio.enhancer import (
    anonymize_text,
    clean_phone_photo,
    enhance_table_html,
    extract_entities,
    merge_cross_page_tables,
    postprocess_french_text,
)
from ocr_studio.exporters import (
    export_csv,
    export_docx,
    export_edited_pdf,
    export_markdown,
    export_png,
    export_searchable_pdf,
)
from ocr_studio.server import app


def test_french_postprocess_fixes_accents_and_compounds():
    raw = "Elément 1 : Editions Tissot et informationconsultation audelà de la limite."
    fixed = postprocess_french_text(raw)
    assert "Élément" in fixed
    assert "Éditions" in fixed
    assert "information-consultation" in fixed
    assert "au-delà" in fixed


def test_merge_multiline_table_rows():
    html_in = """<table>
    <tr><th>Forme</th><th>Qui l'établit</th><th>Décision de la</th><th>Délai de réponse</th></tr>
    <tr><td></td><td></td><td>DREETS</td><td></td></tr>
    <tr><td>Accord collectif majoritaire (syndicats</td><td>Employeur et</td><td>Validation</td><td>15 jours</td></tr>
    <tr><td>représentant 50 % des voix aux</td><td>syndicats</td><td></td><td></td></tr>
    <tr><td>élections du CSE)</td><td></td><td></td><td></td></tr>
    <tr><td>Document unilatéral</td><td>Employeur seul</td><td>Homologation</td><td>21 jours</td></tr>
    </table>"""
    out = enhance_table_html(html_in)
    assert "<th>Décision de la DREETS</th>" in out
    assert "Accord collectif majoritaire (syndicats représentant 50 % des voix aux élections du CSE)" in out
    assert out.count("<tr>") == 3


def test_cross_page_table_merge():
    p1 = [
        {
            "label": "Table",
            "text": "<table><tr><th>Forme</th><th>Délai</th></tr><tr><td></td><td></td></tr></table>",
        }
    ]
    p2 = [
        {
            "label": "Table",
            "text": "<table><tr><th>Forme</th><th>Délai</th></tr><tr><td>Document unilatéral</td><td>21 jours</td></tr></table>",
        },
        {"label": "Text", "text": "Suite du texte."},
    ]
    merged = merge_cross_page_tables([p1, p2])
    assert "Document unilatéral" in merged[0][0]["text"]
    assert merged[0][0]["text"].count("<tr>") == 2
    assert len(merged[1]) == 1


def test_api_ocr_and_exports_on_sample():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}

    sample_path = "/Users/deomimpungu/Desktop/droit des contrats.pdf"
    with open(sample_path, "rb") as f:
        res = client.post(
            "/api/ocr",
            files={"file": ("droit des contrats.pdf", f, "application/pdf")},
            data={"mode": "ocr", "dpi": "200", "postprocess": "true"},
        )
    assert res.status_code == 200
    doc = res.json()
    assert doc["page_count"] == 3
    p1_md = doc["pages"][0]["markdown"]
    # Vérifie que les majuscules accentuées sont corrigées en mode OCR pur
    assert "Élément objectif" in p1_md
    assert "Éditions Tissot" in p1_md
    # Vérifie que le tableau coupé entre p1 et p2 est fusionné en page 1 avec ses cellules multi-lignes regroupées
    assert "Accord collectif majoritaire (syndicats représentant 50 % des voix aux élections du CSE)" in p1_md

    # Vérifie tous les exports, y compris que le PDF searchable reflète les modifications des blocs
    doc["pages"][0]["blocks"][0]["text"] = "MODIFICATION_TEST_123"
    assert len(export_markdown(doc)) > 100
    assert b"Accord collectif majoritaire" in export_csv(doc)
    assert export_docx(doc)[:2] == b"PK"  # ZIP header du .docx
    pdf_bytes = export_searchable_pdf(doc)
    assert pdf_bytes[:4] == b"%PDF"

    import pypdfium2 as pdfium

    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    p0_text = pdf_doc[0].get_textpage().get_text_range()
    pdf_doc.close()
    assert "MODIFICATION_TEST_123" in p0_text

    edited_pdf_bytes = export_edited_pdf(doc)
    assert edited_pdf_bytes[:4] == b"%PDF"
    epdf_doc = pdfium.PdfDocument(edited_pdf_bytes)
    ep0_text = epdf_doc[0].get_textpage().get_text_range()
    epdf_doc.close()
    assert "MODIFICATION_TEST_123" in ep0_text

    img_bytes, img_mime, img_ext = export_png(doc)
    assert img_ext == "zip"  # 3 pages -> zip de PNG
    assert img_bytes[:2] == b"PK"


def test_photo_cleaning_entities_and_anonymize():
    # Image synthétique avec ombre / gradient
    grad = np.tile(np.linspace(120, 240, 200, dtype=np.uint8), (100, 1))
    cleaned = clean_phone_photo(grad)
    assert cleaned.shape == grad.shape

    sample = "Contact : jean.dupont@exemple.fr | Tél : 06 12 34 56 78 | Montant : 1 250,00 € | Date : 12/11/2026"
    ents = extract_entities(sample)
    assert "jean.dupont@exemple.fr" in ents["emails"]
    assert "06 12 34 56 78" in ents["phones"]
    assert any("1 250,00" in a for a in ents["amounts"])
    assert "12/11/2026" in ents["dates"]

    masked = anonymize_text(sample)
    assert "[EMAIL MASQUÉ]" in masked
    assert "[TÉL MASQUÉ]" in masked
    assert "jean.dupont@exemple.fr" not in masked

    client = TestClient(app)
    res = client.post(
        "/api/anonymize",
        json={"pages": [{"blocks": [{"text": sample}], "lines": [{"text": sample}], "text": sample, "markdown": sample}]},
    )
    assert res.status_code == 200
    assert "[EMAIL MASQUÉ]" in res.json()["pages"][0]["blocks"][0]["text"]
