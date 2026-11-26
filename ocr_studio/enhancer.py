"""Prétraitement d'image adaptatif et post-traitement haute précision."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any

import cv2
import numpy as np


# Mots français commençant par une majuscule accentuée souvent lus sans accent par les modèles OCR
_FR_CAP_ACCENT_MAP: dict[str, str] = {
    "Element": "Élément",
    "Elément": "Élément",
    "Elements": "Éléments",
    "Eléments": "Éléments",
    "Edition": "Édition",
    "Editions": "Éditions",
    "Etude": "Étude",
    "Etudes": "Études",
    "Etat": "État",
    "Etats": "États",
    "Egalement": "Également",
    "Ecole": "École",
    "Ecoles": "Écoles",
    "Eglise": "Église",
    "Epoque": "Époque",
    "Etablissement": "Établissement",
    "Etablissements": "Établissements",
    "Evaluation": "Évaluation",
    "Evaluations": "Évaluations",
    "Evolution": "Évolution",
    "Evolutions": "Évolutions",
    "Economie": "Économie",
    "Economique": "Économique",
    "Economiques": "Économiques",
    "Ecriture": "Écriture",
    "Ecrit": "Écrit",
    "Ecrits": "Écrits",
    "Echange": "Échange",
    "Echanges": "Échanges",
    "Epreuve": "Épreuve",
    "Epreuves": "Épreuves",
    "Equipe": "Équipe",
    "Equipes": "Équipes",
    "Etape": "Étape",
    "Etapes": "Étapes",
    "Evenement": "Événement",
    "Evenements": "Événements",
    "Evénement": "Événement",
    "Evénements": "Événements",
    "Etre": "Être",
    "Etant": "Étant",
    "Etaient": "Étaient",
    "Etait": "Était",
    "Echéance": "Échéance",
    "Echeance": "Échéance",
    "Egalité": "Égalité",
    "Egalite": "Égalité",
    "Elaboration": "Élaboration",
    "Election": "Élection",
    "Elections": "Élections",
    "Eligibilité": "Éligibilité",
    "Eligibilite": "Éligibilité",
    "Emission": "Émission",
    "Energie": "Énergie",
    "Enoncé": "Énoncé",
    "Equilibre": "Équilibre",
    "Equivalent": "Équivalent",
    "Erreur": "Erreur",
    "Etablir": "Établir",
    "Etendue": "Étendue",
    "Exécution": "Exécution",
}

# Mots composés dont le trait d'union est parfois avalé lors du recollage de fin de ligne
_COMPOUND_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\binformationconsultation\b", re.IGNORECASE), "information-consultation"),
    (re.compile(r"\baudela\b", re.IGNORECASE), "au-delà"),
    (re.compile(r"\baudelà\b"), "au-delà"),
    (re.compile(r"\bAudelà\b"), "Au-delà"),
    (re.compile(r"\bcestadire\b", re.IGNORECASE), "c'est-à-dire"),
    (re.compile(r"\bc'estàdire\b", re.IGNORECASE), "c'est-à-dire"),
    (re.compile(r"\bvisàvis\b", re.IGNORECASE), "vis-à-vis"),
    (re.compile(r"\bpeutêtre\b", re.IGNORECASE), "peut-être"),
    (re.compile(r"\bPeutêtre\b"), "Peut-être"),
    (re.compile(r"\bnonobstant\b", re.IGNORECASE), "nonobstant"),
    (re.compile(r"\bsousjacent\b", re.IGNORECASE), "sous-jacent"),
    (re.compile(r"\bsousjacents\b", re.IGNORECASE), "sous-jacents"),
    (re.compile(r"\bcijoint\b", re.IGNORECASE), "ci-joint"),
    (re.compile(r"\bcidessous\b", re.IGNORECASE), "ci-dessous"),
    (re.compile(r"\bcidessus\b", re.IGNORECASE), "ci-dessus"),
    (re.compile(r"\bavantpropos\b", re.IGNORECASE), "avant-propos"),
    (re.compile(r"\bcomptetenu\b", re.IGNORECASE), "compte tenu"),
]

_CAP_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_FR_CAP_ACCENT_MAP, key=len, reverse=True)) + r")\b"
)


def enhance_image_for_ocr(gray: np.ndarray, upscale: float = 1.0) -> np.ndarray:
    """Améliore le contraste local et la netteté d'une image en niveaux de gris pour l'OCR."""
    img = gray
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if upscale > 1.01:
        img = cv2.resize(
            img,
            None,
            fx=upscale,
            fy=upscale,
            interpolation=cv2.INTER_CUBIC,
        )

    # Débruitage léger préservant les contours des caractères
    denoised = cv2.fastNlMeansDenoising(img, None, h=5, templateWindowSize=7, searchWindowSize=21)

    # Égalisation adaptative du contraste (CLAHE) pour les scans pâles ou ombragés
    clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)

    # Accentuation douce (unsharp mask)
    blurred = cv2.GaussianBlur(contrasted, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(contrasted, 1.25, blurred, -0.25, 0)
    return sharpened


def clean_phone_photo(gray: np.ndarray) -> np.ndarray:
    """Supprime les ombres et l'éclairage inégal d'une photo de document prise au téléphone."""
    img = gray
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Estimation du fond lumineux par dilatation + flou médian large
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    bg = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
    bg = cv2.medianBlur(bg, 21)

    # Normalisation par division (rend le papier uniformément blanc)
    diff = cv2.divide(img.astype(np.float32), np.maximum(bg.astype(np.float32), 1.0), scale=255.0)
    norm = np.clip(diff, 0, 255).astype(np.uint8)
    return enhance_image_for_ocr(norm, upscale=1.0)


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:0[1-9](?:[\s.-]?\d{2}){4}|\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4})")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]{4}){3,7}\b")
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:janv\.?|janvier|févr\.?|février|mars|avr\.?|avril|mai|juin|juil\.?|juillet|août|sept\.?|septembre|oct\.?|octobre|nov\.?|novembre|déc\.?|décembre)\s+\d{2,4})\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"(?:\d[\d\s.,]*\s?(?:€|EUR|\$|USD)|\$\s?\d[\d\s.,]*)",
    re.IGNORECASE,
)


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extrait les entités clés d'un texte (emails, téléphones, IBAN, dates, montants)."""
    def _uniq(matches: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in matches:
            s = m.strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    return {
        "emails": _uniq(_EMAIL_RE.findall(text)),
        "phones": _uniq(_PHONE_RE.findall(text)),
        "ibans": _uniq(_IBAN_RE.findall(text)),
        "dates": _uniq(_DATE_RE.findall(text)),
        "amounts": _uniq(_AMOUNT_RE.findall(text)),
    }


def anonymize_text(text: str) -> str:
    """Masque les données personnelles (emails, téléphones, IBAN) dans un texte."""
    if not text:
        return text
    out = _EMAIL_RE.sub("[EMAIL MASQUÉ]", text)
    out = _IBAN_RE.sub("[IBAN MASQUÉ]", out)
    out = _PHONE_RE.sub("[TÉL MASQUÉ]", out)
    return out


def postprocess_french_text(text: str) -> str:
    """Corrige les erreurs fréquentes de majuscules accentuées et de césures collées."""
    if not text:
        return text

    out = _CAP_PATTERN.sub(lambda m: _FR_CAP_ACCENT_MAP.get(m.group(1), m.group(1)), text)
    for pat, repl in _COMPOUND_FIXES:
        out = pat.sub(repl, out)
    # Espaces multiples accidentels
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


class _TableParser(HTMLParser):
    """Parse un tableau HTML simple en liste de rangées [(is_header, [cells])]."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[bool, list[str]]] = []
        self._in_tr = False
        self._in_cell = False
        self._cell_is_th = False
        self._cur_row: list[str] = []
        self._cur_row_th = False
        self._cur_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "tr":
            self._in_tr = True
            self._cur_row = []
            self._cur_row_th = False
        elif t in ("td", "th") and self._in_tr:
            self._in_cell = True
            self._cell_is_th = t == "th"
            if self._cell_is_th:
                self._cur_row_th = True
            self._cur_cell = []
        elif t == "br" and self._in_cell:
            self._cur_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th") and self._in_cell:
            self._in_cell = False
            cell_txt = postprocess_french_text("".join(self._cur_cell).strip())
            self._cur_row.append(cell_txt)
        elif t == "tr" and self._in_tr:
            self._in_tr = False
            if self._cur_row:
                self.rows.append((self._cur_row_th, self._cur_row))

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cur_cell.append(data)


def parse_html_table(table_html: str) -> list[tuple[bool, list[str]]]:
    """Extrait les rangées d'un tableau HTML."""
    parser = _TableParser()
    parser.feed(table_html)
    parser.close()
    return parser.rows


def _join_cell_fragments(prev: str, nxt: str) -> str:
    if not prev:
        return nxt
    if not nxt:
        return prev
    if prev.endswith("-"):
        return prev[:-1] + nxt
    return f"{prev} {nxt}"


def merge_multiline_table_rows(rows: list[tuple[bool, list[str]]]) -> list[tuple[bool, list[str]]]:
    """Fusionne les rangées fragmentées issues de cellules multi-lignes.

    Heuristique :
    - Normalise la largeur des rangées au nombre maximal de colonnes.
    - Une rangée suivante est fusionnée dans la précédente si :
      * les deux sont des en-têtes (<th>), OU
      * la colonne 0 (ou la majorité des colonnes) est vide dans la nouvelle rangée
        alors qu'une autre colonne contient la suite du texte, OU
      * dans une rangée de données, la cellule précédente ne se termine pas par une
        ponctuation forte et au moins une colonne est vide (wrap partiel).
    """
    if len(rows) <= 1:
        return rows

    ncols = max(len(r[1]) for r in rows)
    norm: list[tuple[bool, list[str]]] = [
        (is_th, cells + [""] * (ncols - len(cells))) for is_th, cells in rows
    ]

    merged: list[tuple[bool, list[str]]] = [norm[0]]
    for is_th, cells in norm[1:]:
        prev_th, prev_cells = merged[-1]
        non_empty = [i for i, c in enumerate(cells) if c.strip()]
        if not non_empty:
            continue

        # Cas 1 : Suite d'un en-tête (<tr><th>...</th></tr> suivi de <tr><th>...</th></tr> ou <tr><td>...</td></tr> avec cellules vides)
        if prev_th and (is_th or (len(non_empty) < ncols and not cells[0].strip())):
            merged[-1] = (
                True,
                [_join_cell_fragments(prev_cells[i], cells[i]) for i in range(ncols)],
            )
            continue

        # Cas 2 : Rangée de données dont la 1ère colonne est vide (continuation)
        # ou dont plusieurs colonnes sont vides alors que la ligne précédente
        # avait du texte dans ces colonnes
        prev_non_empty = [i for i, c in enumerate(prev_cells) if c.strip()]
        is_partial_continuation = (
            not is_th
            and not prev_th
            and len(non_empty) < ncols
            and (
                not cells[0].strip()
                or (
                    len(prev_non_empty) >= 2
                    and any(
                        prev_cells[i].strip()
                        and not prev_cells[i].rstrip().endswith((".", "!", "?", ")", "]"))
                        for i in non_empty
                    )
                )
            )
        )

        # Cas spécial : si la colonne 0 est remplie et toutes les autres sont vides,
        # mais que la ligne précédente avait déjà du contenu en col 0 sans ponctuation finale
        # et du contenu dans les autres colonnes (ex: "élections du CSE)" sur une 3e ligne)
        col0_wrap = (
            not is_th
            and not prev_th
            and non_empty == [0]
            and len(prev_non_empty) >= 2
            and prev_cells[0].strip()
            and not prev_cells[0].rstrip().endswith((".", "!", "?"))
        )

        if is_partial_continuation or col0_wrap:
            merged[-1] = (
                prev_th,
                [_join_cell_fragments(prev_cells[i], cells[i]) for i in range(ncols)],
            )
        else:
            merged.append((is_th, cells))

    return merged


def rows_to_html_table(rows: list[tuple[bool, list[str]]]) -> str:
    """Sérialise des rangées normalisées en <table> HTML propre."""
    if not rows:
        return ""
    parts = ["<table>"]
    for is_th, cells in rows:
        tag = "th" if is_th else "td"
        tds = "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in cells)
        parts.append(f"<tr>{tds}</tr>")
    parts.append("</table>")
    return "\n".join(parts)


def enhance_table_html(table_html: str) -> str:
    """Nettoie et fusionne les cellules multi-lignes d'un tableau HTML."""
    rows = parse_html_table(table_html)
    if not rows:
        return table_html
    merged = merge_multiline_table_rows(rows)
    return rows_to_html_table(merged)


def merge_cross_page_tables(pages_blocks: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    """Fusionne un tableau coupé entre la fin d'une page et le début de la suivante.

    Si le dernier bloc de la page N est un `Table` (souvent juste l'en-tête) et le
    premier bloc de la page N+1 est un `Table` avec le même nombre de colonnes,
    on fusionne la suite dans le premier tableau (en évitant de dupliquer l'en-tête).
    """
    if len(pages_blocks) <= 1:
        return pages_blocks

    for idx in range(len(pages_blocks) - 1):
        cur_blocks = pages_blocks[idx]
        nxt_blocks = pages_blocks[idx + 1]
        if not cur_blocks or not nxt_blocks:
            continue
        last_b = cur_blocks[-1]
        first_b = nxt_blocks[0]
        if last_b.get("label") != "Table" or first_b.get("label") != "Table":
            continue

        rows_a = parse_html_table(last_b.get("text", ""))
        rows_b = parse_html_table(first_b.get("text", ""))
        if not rows_a or not rows_b:
            continue

        ncols_a = max(len(r[1]) for r in rows_a)
        ncols_b = max(len(r[1]) for r in rows_b)
        if ncols_a != ncols_b:
            continue

        # Si l'en-tête est répété sur la page suivante, on le retire
        if rows_a[0][1] == rows_b[0][1]:
            rows_b = rows_b[1:]

        combined = merge_multiline_table_rows(rows_a + rows_b)
        last_b["text"] = rows_to_html_table(combined)
        last_b["merged_from_next_page"] = True
        nxt_blocks.pop(0)

    return pages_blocks
