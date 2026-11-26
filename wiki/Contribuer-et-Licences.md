# Contribuer et Licences

## Lancer la suite de tests

Les tests unitaires et d'intégration (moteur, post-traitement, API FastAPI, exports) se trouvent dans `tests/test_ocr_studio.py` :

```bash
.venv/bin/pytest -v
```

---

## Contribuer au projet

Les contributions sont les bienvenues ! Pour proposer une amélioration ou un correctif :

1. Forkez le dépôt et créez une branche dédiée (`feat/...` ou `fix/...`).
2. Respectez l'organisation modulaire (`engine.py`, `enhancer.py`, `exporters.py`, `server.py`, `static/`).
3. Ajoutez ou mettez à jour les tests dans `tests/test_ocr_studio.py`.
4. Assurez-vous qu'aucun fichier personnel ou document sensible (`.pdf`, `.png`, `.docx`, `.env`, etc.) n'est inclus dans vos commits (voir `.gitignore`).
5. Ouvrez une Pull Request claire en décrivant les modifications et les tests exécutés.

Pour plus de détails, consultez [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Auteur

Projet créé et réalisé par **Deo Mimpungu**.

---

## Licences

- **OCR Studio** : distribué sous licence **Apache-2.0** (voir [LICENSE](../LICENSE)).
- **Indra OCR** (moteur sous-jacent par Datalab) :
  - Code source sous licence **Apache-2.0** ([github.com/datalab-to/indra](https://github.com/datalab-to/indra))
  - Modèles ONNX sous licence **OpenRAIL-M** ([huggingface.co/datalab-to/indra-ocr](https://huggingface.co/datalab-to/indra-ocr))
