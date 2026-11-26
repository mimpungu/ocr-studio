# Guide d'Utilisation

## 1. Importer un document

Glissez-déposez un **PDF** ou une **image** dans la zone prévue à cet effet, puis ajustez les paramètres dans le panneau de gauche.

### Options de traitement

- **Source** :
  - `Auto` : exploite la couche texte des PDF numériques si elle est fiable, sinon bascule sur l'OCR visuel.
  - `OCR` : ignore la couche texte et analyse toute la page visuellement.
  - `Couche texte` : force la lecture directe de la couche texte du PDF.
- **Haute précision FR / Tableaux** *(activé par défaut)* : fusionne les cellules multi-lignes dans les tableaux HTML, raccorde les tableaux coupés entre deux pages et corrige les majuscules accentuées et mots composés français.
- **Scan difficile (CLAHE)** : applique débruitage, contraste local CLAHE et accentuation pour les vieux scans.
- **Photo téléphone (ombres)** : supprime les ombres et uniformise l'éclairage sur les documents photographiés au smartphone.
- **Math en LaTeX** : active la reconnaissance des formules mathématiques au format `$...$`.
- **DPI (`150` / `200` / `300`)** : augmentez à `300` pour les documents contenant de très petits caractères.

---

## 2. Re-OCR ciblé par zone

Si une zone précise reste floue ou mal reconnue :

1. Activez l'outil **Sélection** (`✂️`) au-dessus de l'aperçu de la page.
2. Tracez un rectangle autour de la zone concernée.
3. OCR Studio découpe la région, applique un agrandissement (`upscale x2`) et un renforcement de contraste, puis relance l'OCR sur cette zone.

---

## 3. Éditeur interactif côte à côte

Dans le panneau de droite, l'onglet **Éditeur direct** permet de :

- Modifier le texte de chaque bloc directement.
- Changer le type d'un bloc (`Section-Header`, `Text`, `Table`, `List-Group`, etc.).
- Réorganiser l'ordre des blocs avec **`↑` / `↓`** ou en ajouter avec **`+ Bloc`**.
- Éditer les tableaux cellule par cellule (**`+ Ligne`**, **`+ Colonne`**).
- Utiliser **Rechercher & Remplacer** sur l'ensemble des pages.
- Annuler la dernière action avec **`↶ Annuler`**.

---

## 4. Outils métier & Anonymisation RGPD

- Extraction automatique d'entités clés (emails, téléphones, dates, montants, IBAN).
- Bouton **`🔒 Anonymiser (RGPD)`** : masque automatiquement emails, numéros de téléphone et IBAN dans tout le document avant export ou partage.

---

## 5. Exports multi-formats

Depuis le menu **`Export ▾`** en haut à droite :

| Format | Description |
| :--- | :--- |
| **PDF** | Génère un PDF propre intégrant toutes vos modifications |
| **Word (`.docx`)** | Document Word avec titres et vrais tableaux |
| **Image (`.png` / `.zip`)** | Image PNG (1 page) ou archive ZIP de PNG (multi-pages) |
| **Markdown (`.md`)** | Export Markdown structuré |
| **Texte (`.txt`)** | Texte brut |
| **JSON (`.json`)** | Données structurées (blocs, lignes, options, métadonnées) |

*(L'API backend supporte également l'export **CSV** et le **PDF searchable**.)*
