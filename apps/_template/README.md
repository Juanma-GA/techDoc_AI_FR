# TEMPLATE

Squelette canonique pour démarrer un nouveau POC. Conforme à [`STANDARD_POC.md`](../../STANDARD_POC.md).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

## Ce que le template fournit d'office

Quand tu copies ce template, tu obtiens déjà :

- **Backend FastAPI** prêt à l'emploi : `/api/v1/health`, `/api/v1/settings` (config Mistral runtime), `/api/v1/admin/stats` + `/api/v1/admin/reset/all`
- **Client Mistral** générique (`core/mistral_client.py`) en httpx async + sync
- **Modèle `AppConfig`** + migration Alembic initiale pour stocker la clé Mistral en SQLite
- **Preview HTML autonome** (`backend/app/templates/preview.html`) servi à `/` quand `frontend/dist/` n'existe pas — UI vanilla JS avec onglets Home / Architecture / Données / Paramètres, theme toggle, design-tokens injectés
- **Wrapper `start.bat` + `_run.bat`** ASCII pur, fenêtre persistante (`cmd /k`), port vérifié avant bind
- **Wrapper `package.bat` + `_package.bat`** qui appelle `scripts/package_TEMPLATE.py`

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Le script :

1. Détecte Python 3.11+ (system, embed, ou installer silencieux).
2. Crée le venv `backend/.venv/`.
3. Installe les deps Python.
4. Applique les migrations Alembic.
5. Vérifie que le port (8000 par défaut) est libre.
6. Lance uvicorn sur `http://127.0.0.1:8000/` et ouvre le navigateur sur la preview HTML.

Pour le frontend en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:TEMPLATE
```

## Adaptation pour un nouveau POC

```bash
cp -r apps/_template apps/<nouveau-poc>
```

Puis, dans l'ordre :

### 1. Renommer les identifiants

| Fichier | À modifier |
|---|---|
| `apps/<poc>/backend/pyproject.toml` | `name = "<poc>-backend"` + adapter `description` |
| `apps/<poc>/backend/app/config.py` | `app_name = "<poc>"`, `database_url` (`data/<poc>.db`) |
| `apps/<poc>/backend/alembic.ini` | `sqlalchemy.url = sqlite:///./data/<poc>.db` |
| `apps/<poc>/backend/.env.example` | `APP_NAME`, `DATABASE_URL` |
| `apps/<poc>/frontend/package.json` | `"name": "@apps/<poc>-frontend"` |
| `apps/<poc>/frontend/index.html` | `<title><poc></title>` |
| `apps/<poc>/frontend/src/locales/{fr,en}.json` | `app.title` |
| `apps/<poc>/README.md` | titre + bind + palier |

### 2. Choisir un port unique

| Fichier | À modifier |
|---|---|
| `apps/<poc>/_run.bat` | `set "PORT=80XX"` (XX libre dans le repo) |
| `apps/<poc>/start.sh` | `PORT="${PORT:-80XX}"` |
| `apps/<poc>/frontend/vite.config.ts` | proxy `"/api": "http://127.0.0.1:80XX"` |

### 3. Adapter le packaging

```bash
cp scripts/package_TEMPLATE.py scripts/package_<poc>.py
```

Puis adapter en tête de `scripts/package_<poc>.py` :
- `APP_NAME = "<poc>"`
- `APP_SLUG = "<poc>"` (nom du dossier sous apps/)
- `EMBED_PREFIX = "<poc>"`
- `_LISEZ_MOI` et `_PACKAGE_README` : adapter au métier du POC

Mettre à jour `apps/<poc>/_package.bat` pour appeler `scripts/package_<poc>.py`.

### 4. Ajouter ta logique métier

| Étape | Fichier |
|---|---|
| Tables métier | `backend/app/db/models.py` (en plus de `AppConfig`) |
| Migration | `backend/alembic/versions/0002_<feature>.py` |
| Schémas Pydantic | `backend/app/schemas.py` |
| Routes métier | `backend/app/api/<feature>.py` + register dans `main.py` |
| Compteurs | `backend/app/api/admin.py` (étendre `stats()` et `reset_all()` pour tes tables) |
| UI preview | `backend/app/templates/preview.html` (remplacer page Home + ajouter onglets métier) |
| Workflow Architecture | `backend/app/templates/preview.html` section `renderArchitecture` |
| Tests | `backend/tests/test_<feature>.py` |

### 5. Wirer dans le monorepo

| Fichier | À modifier |
|---|---|
| `package.json` racine | Ajouter scripts `dev:<poc>`, `test:e2e:<poc>`, `openapi:gen:<poc>` |

### 6. Vérification

```bash
bash scripts/check_standard.sh    # doit retourner exit 0
cd apps/<poc>/backend && pytest   # doit être vert
```

## Écarts au standard

Aucun par défaut. Documenter ici tout écart introduit dans un POC instancié à partir de ce template.
