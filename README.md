# OCR Studio

**OCR Studio** est un outil privé et local d'OCR, d'édition documentaire et d'export multi-formats basé sur `indra-ocr` (ONNX Runtime sur CPU, sans GPU ni PyTorch).

Il ajoute par-dessus le moteur de base :
- **Prétraitement adaptatif** : mode *Scan difficile* (débruitage + contraste CLAHE + accentuation) et mode *Photo téléphone* (suppression des ombres et uniformisation de l'éclairage).
- **Post-traitement haute précision** : fusion des cellules multi-lignes dans les tableaux HTML, raccordement des tableaux coupés entre deux pages, restauration des majuscules accentuées françaises (`É`, `À`, `È`...) et des mots composés.
- **Éditeur interactif côte à côte** : modification directe des blocs et des tableaux cellule par cellule (`+ Ligne`, `+ Colonne`, `↑`/`↓`, `Rechercher & Remplacer`, `Annuler`).
- **Re-OCR ciblé par zone** : sélection rectangulaire sur l'image pour relire une zone difficile en haute résolution (`upscale x2` + contraste).
- **Outils métier & RGPD** : extraction automatique de champs clés (emails, téléphones, dates, montants, IBAN) et anonymisation en un clic.
- **Exports complets** : **PDF**, **Word (`.docx`)**, **Image (`.png` / `.zip`)**, **Markdown (`.md`)**, **Texte (`.txt`)**, **JSON (`.json`)**.

---

## Architecture globale

```mermaid
flowchart LR
    U["Utilisateur (Navigateur)"] -->|"PDF / Image + Options"| UI["Interface Web (index.html / app.js)"]
    UI -->|"HTTP /api/ocr, /api/ocr-region, /api/anonymize, /api/export/*"| API["FastAPI (ocr_studio/server.py)"]

    subgraph Backend["Coeur Python (ocr_studio)"]
        API --> ENG["Moteur OCR (engine.py)"]
        ENG -->|"Prétraitement Scan / Photo"| ENH["Amélioration & RGPD (enhancer.py)"]
        ENG -->|"Inférence CPU"| INDRA["indra-ocr (ONNX Runtime)"]
        INDRA --> ENH
        API --> EXP["Exportateurs (exporters.py)"]
    end

    EXP -->|"PDF / DOCX / PNG / MD / TXT / JSON"| UI
```

---

## Flux de traitement (Pipeline OCR & Édition)

```mermaid
sequenceDiagram
    actor User as Utilisateur
    participant UI as Interface Web
    participant API as FastAPI (server.py)
    participant Eng as Moteur (engine.py)
    participant Enh as Enhancer (enhancer.py)
    participant Exp as Exporters (exporters.py)

    User->>UI: Dépose un PDF ou une image
    UI->>API: POST /api/ocr (mode, dpi, photo_mode, enhance_scan, math)
    API->>Eng: process_document(...)
    Eng->>Eng: Rendu PDF (pypdfium2) / Lecture image
    opt Mode Scan difficile ou Photo téléphone
        Eng->>Enh: clean_phone_photo() / enhance_image_for_ocr()
    end
    Eng->>Eng: Exécution indra-ocr (ONNX Runtime)
    opt Haute précision activée
        Eng->>Enh: enhance_table_html() + postprocess_french_text()
        Eng->>Enh: merge_cross_page_tables() + extract_entities()
    end
    Eng-->>API: JSON structuré (pages, blocs, lignes, entités, images)
    API-->>UI: Affiche document + blocs éditables côte à côte

    User->>UI: Édite blocs/tableaux, Re-OCR zone ou Anonymise
    User->>UI: Clique sur Export -> PDF / Word / Image / MD / TXT / JSON
    UI->>API: POST /api/export/{fmt} (document édité)
    API->>Exp: export_edited_pdf / export_docx / export_png / ...
    Exp-->>UI: Téléchargement direct du fichier
```

---

## Structure du projet

```text
ocr-studio/
├── pyproject.toml               # Dépendances et point d'entrée CLI (`ocr-studio`)
├── README.md                    # Documentation technique et architecture
├── LICENSE                      # Licence Apache-2.0
├── CONTRIBUTING.md              # Guide de contribution au projet
├── GUIDE_LANCEMENT.md           # Guide pas-à-pas de lancement et d'utilisation
├── ocr_studio/
│   ├── __init__.py
│   ├── server.py                # Serveur FastAPI, routes /api/* et encodage UTF-8 des exports
│   ├── engine.py                # Orchestration indra-ocr, rendu PDF, Re-OCR ciblé par zone
│   ├── enhancer.py              # Prétraitement photo/scan, fusion tableaux, accents FR, RGPD
│   ├── exporters.py             # Exports PDF édité, PDF searchable, Word, PNG/ZIP, CSV, MD, TXT, JSON
│   └── static/
│       ├── index.html           # Structure de l'interface (style Indra OCR)
│       ├── style.css            # Feuille de style claire (palette oklch, layout 2 colonnes)
│       └── app.js               # Éditeur de blocs/tableaux, overlays SVG, lasso Re-OCR, Undo
└── tests/
    └── test_ocr_studio.py       # Tests unitaires et d'intégration API/exports
```

---

## Démarrage rapide

Consultez le guide détaillé dans [GUIDE_LANCEMENT.md](GUIDE_LANCEMENT.md) ou lancez directement :

```bash
cd /Users/deomimpungu/Development/ocr-studio
.venv/bin/ocr-studio --port 8770
```

Ouvrez ensuite **http://127.0.0.1:8770** dans votre navigateur.

---

## Contribuer

Les contributions (correctifs, améliorations OCR, nouveaux exports, UI, documentation) sont les bienvenues. Consultez le guide [CONTRIBUTING.md](CONTRIBUTING.md) pour installer l'environnement de développement, lancer les tests (`pytest`) et soumettre une Pull Request.

---

## Auteur

Réalisé par **Deo Mimpungu**.

---

## Licence & Crédits

- **OCR Studio** est distribué sous licence **Apache-2.0** — voir [LICENSE](LICENSE).
- Le moteur OCR repose sur **[Indra OCR] (Datalab).
