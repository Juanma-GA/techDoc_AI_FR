# TEMPLATE

> **CE README EST CELUI DU TEMPLATE — À RÉÉCRIRE INTÉGRALEMENT après instanciation.**
>
> Pour créer un nouveau POC, **n'éditez pas ce fichier**. Lancez à la place :
>
> ```bash
> bash scripts/new_poc.sh <slug> [<port>]
> ```
>
> Le script copie ce template, fait les substitutions, et écrase
> `apps/<slug>/README.md` par un stub propre que vous remplirez avec la
> description métier de votre POC (cf. `apps/doc-writer/README.md` ou
> `apps/doc-reviewer/README.md` comme références).

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

Voir [`STANDARD_POC.md` §11](../../STANDARD_POC.md#11-ajout-dun-nouveau-poc).
Deux méthodes y sont documentées :

- **Recommandée** : `bash scripts/new_poc.sh <slug> [<port>]` — automatise les ~15 substitutions et passe `check_standard.sh`.
- **Manuelle (fallback)** : liste exhaustive des fichiers à éditer si le script n'est pas utilisable.

Après instanciation, les étapes restant à la charge du dev (logique métier, migration, routes, preview) sont listées dans le stub de README généré par le script.

## Écarts au standard

Aucun par défaut. Documenter ici tout écart introduit dans un POC instancié à partir de ce template.
