# Installation et Lancement

## Prérequis

- **Python 3.10** ou supérieur
- Aucun GPU requis (inférence CPU via ONNX Runtime)
- **Première exécution** : une connexion Internet est nécessaire une seule fois pour télécharger les modèles ONNX d'Indra OCR (~76 Mo) dans le cache Hugging Face. Toutes les exécutions suivantes fonctionnent **100 % hors-ligne**.

---

## Installation depuis les sources

```bash
git clone <url-du-depot>
cd ocr-studio

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

Pour installer également les dépendances de test (`pytest`, `httpx`) :

```bash
pip install -e ".[test]"
```

---

## Lancer le serveur web

```bash
.venv/bin/ocr-studio --port 8770
```

Options disponibles en ligne de commande :

| Option | Défaut | Description |
| :--- | :--- | :--- |
| `--host` | `127.0.0.1` | Adresse d'écoute du serveur FastAPI |
| `--port` | `8770` | Port HTTP d'écoute |

Une fois démarré, ouvrez **http://127.0.0.1:8770** dans votre navigateur.

Pour arrêter le serveur, utilisez `Ctrl + C` dans le terminal.
