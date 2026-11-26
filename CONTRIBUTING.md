# Contribuer à OCR Studio

Merci pour votre intérêt pour **OCR Studio** (réalisé par **Deo Mimpungu**). Toutes les contributions sont les bienvenues : corrections de bugs, améliorations du prétraitement/post-traitement OCR, nouveaux formats d'export, améliorations de l'interface web ou documentation.

---

## 1. Prérequis et installation locale

Assurez-vous d'avoir **Python >= 3.10** installé, puis configurez l'environnement virtuel avec les dépendances de développement et de test :

```bash
git clone https://github.com/mimpungu/ocr-studio.git
cd ocr-studio

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[test]"
```

Lancer le serveur en local pour tester vos modifications :

```bash
ocr-studio --port 8770
```

---

## 2. Lancer les tests

Avant de proposer une modification, vérifiez que la suite de tests passe sans erreur :

```bash
pytest
```

Si vous ajoutez une nouvelle fonctionnalité ou corrigez un bug, ajoutez ou mettez à jour les tests correspondants dans [tests/test_ocr_studio.py](tests/test_ocr_studio.py).

---

## 3. Processus de contribution

1. **Forkez** le dépôt et créez une branche dédiée depuis `main` :
   ```bash
   git checkout -b feat/ma-fonctionnalite
   # ou
   git checkout -b fix/mon-correctif
   ```
2. **Effectuez vos modifications** en respectant la structure du projet :
   - `ocr_studio/engine.py` : orchestration OCR et rendu PDF
   - `ocr_studio/enhancer.py` : prétraitement image, post-traitement texte/tableaux, RGPD
   - `ocr_studio/exporters.py` : génération des exports (PDF, DOCX, PNG, MD, TXT, CSV, JSON)
   - `ocr_studio/server.py` : routes FastAPI
   - `ocr_studio/static/` : interface web (`index.html`, `style.css`, `app.js`)
3. **Vérifiez** qu'aucune donnée personnelle, fichier de test sensible (`.pdf`, `.png`, `.docx`, `.env`, etc.) ou cache n'est ajouté au commit (voir `.gitignore`).
4. **Committez** avec des messages clairs et concis (ex. `feat: ...`, `fix: ...`, `docs: ...`).
5. **Ouvrez une Pull Request** en décrivant le contexte, les changements apportés et les tests effectués.

---

## 4. Signaler un bug ou proposer une idée

Lorsque vous ouvrez une issue :
- Décrivez le comportement attendu et le comportement observé.
- Indiquez votre version de Python et votre système d'exploitation.
- Ne joignez jamais de documents contenant des données personnelles ou confidentielles.

---

## Auteur

Projet créé et réalisé par **Deo Mimpungu**.
