# Wiki — OCR Studio

Bienvenue sur le Wiki officiel d'**OCR Studio**, l'outil privé et local d'OCR, d'édition documentaire interactive et d'export multi-formats propulsé par `indra-ocr` (ONNX Runtime sur CPU, sans GPU ni PyTorch).

---

## Navigation rapide

- **[Installation et Lancement](Installation-et-Lancement)** — Prérequis, configuration de `.venv`, démarrage du serveur CLI et fonctionnement hors-ligne.
- **[Guide d'Utilisation](Guide-Utilisation)** — Prétraitement scan/photo, Re-OCR ciblé par zone, éditeur côte à côte, anonymisation RGPD et exports.
- **[Architecture et API](Architecture-et-API)** — Fonctionnement interne des modules Python et référence des endpoints FastAPI.
- **[Contribuer et Licences](Contribuer-et-Licences)** — Lancer les tests (`pytest`), bonnes pratiques de contribution, auteur et licences.

---

## Aperçu des fonctionnalités

| Domaine | Capacités |
| :--- | :--- |
| **Moteur OCR** | CPU uniquement via `indra-ocr` (ONNX Runtime), 80+ langues, lecture de couche texte PDF ou OCR visuel |
| **Prétraitement** | Mode *Scan difficile* (débruitage + CLAHE + accentuation) et mode *Photo téléphone* (suppression des ombres) |
| **Post-traitement** | Fusion de cellules multi-lignes, raccordement des tableaux inter-pages, majuscules accentuées FR |
| **Édition interactive** | Éditeur côte à côte bloc par bloc, édition de tableaux cellule par cellule, `Rechercher & Remplacer`, `Annuler` |
| **Re-OCR ciblé** | Lasso rectangulaire sur l'image avec `upscale x2` + amélioration de contraste |
| **Outils métier & RGPD** | Extraction d'entités (emails, téléphones, dates, montants, IBAN) et anonymisation en un clic |
| **Exports** | PDF édité, PDF searchable, Word (`.docx`), Image (`.png` / `.zip`), Markdown (`.md`), Texte (`.txt`), CSV, JSON |

---

## Auteur

Projet créé et réalisé par **Deo Mimpungu**.
