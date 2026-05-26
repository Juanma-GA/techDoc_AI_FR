# ocr-vision

POC d'**OCR + reconnaissance visuelle** sur des documents techniques :
à partir d'une image (PNG/JPG) ou d'un PDF, le backend envoie le fichier
aux modèles Mistral (`/v1/ocr` + modèle multimodal) et renvoie en
parallèle :

- le **texte transcrit** par l'OCR,
- une **description en français** du contenu visible (objets,
  équipements, schémas, pictogrammes, texte visible).

OCR et reconnaissance sont indépendants : si l'un échoue, l'autre peut
quand même remonter.

Conforme à [`STANDARD_POC.md`](../../STANDARD_POC.md). Bootstrap depuis
[`apps/_template`](../_template/).

## État actuel du POC

**Périmètre minimal** : un seul endpoint métier (`POST /api/v1/vision/test`)
qui valide la chaîne OCR + multimodal Mistral. Pas encore de persistance
des analyses ni de workflow utilisateur — c'est une brique de validation
technique, pas une app complète à ce stade.

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| LLM | Mistral via `httpx` async (OCR `/v1/ocr` + modèle multimodal), pas de SDK |
| Frontend | React 18 + TS + Vite + Tailwind + RHF + Zod + i18next + Zustand + TanStack Query |
| UI | `@internal/ui` exclusivement |
| Persistance | SQLite par défaut (`backend/data/ocr-vision.db`), Alembic dès J1 |

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Le script :

1. Détecte Python 3.11+
2. Crée le venv `backend/.venv/`
3. Installe les deps Python
4. Applique les migrations Alembic
5. Lance uvicorn sur `http://127.0.0.1:8003/`

Pour le frontend en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:ocr-vision
```

## Endpoint métier

`POST /api/v1/vision/test` — multipart/form-data

| Champ | Type | Description |
|---|---|---|
| `file` | file (image/* ou application/pdf) | Le document à analyser |
| `prompt` | string (optionnel) | Prompt custom pour la reconnaissance visuelle (par défaut : description FR en 3-5 phrases) |

Réponse :

```json
{
  "ocr_text": "...",
  "description": "...",
  "errors": []
}
```

`errors` liste les erreurs partielles (ex. OCR a échoué mais description OK).

La clé Mistral est lue depuis la table `app_config` (configurable via
l'onglet **Paramètres** du preview ou via `POST /api/v1/settings`).

## Écarts au standard

Aucun.

## Tests

```bash
# Backend
cd backend && pytest

# Frontend (Vitest unitaire)
pnpm --filter @apps/ocr-vision-frontend test

# E2E Playwright
pnpm --filter @apps/ocr-vision-frontend test:e2e
```

Conformité :

```bash
bash scripts/check_standard.sh
```
