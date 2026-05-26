# Internal POC Monorepo

Monorepo interne hébergeant plusieurs POC IA full-stack (FastAPI + React),
développés dans un **tronc commun partagé** (`packages/ui`, `design-tokens/`,
scripts, standard) et conformes à [`STANDARD_POC.md`](STANDARD_POC.md).
Chaque app est indépendante côté runtime mais s'aligne sur les mêmes
règles, les mêmes composants UI et les mêmes tokens.

| App | Rôle | Port |
|---|---|---|
| [`apps/ftm/`](apps/ftm/) | FTM Agent v2 — analyse de Fiches de Tâches de Maintenance | 8000 |
| [`apps/pdf-reviewer/`](apps/pdf-reviewer/) | Détection et correction d'anomalies dans des PDF techniques | 8001 |
| [`apps/doc-writer/`](apps/doc-writer/) | Génération de contenu rédactionnel en RAG streaming | 8002 |
| [`apps/ocr-vision/`](apps/ocr-vision/) | OCR + extraction visuelle sur documents techniques | 8003 |
| [`apps/_template/`](apps/_template/) | Squelette canonique à copier pour démarrer un nouveau POC | — |

> **Principe directeur** : ces apps sont des **POC local-first stricts**
> — ils tournent localement sur le PC du dev. Pas de Docker, pas de CI,
> pas de déploiement dans le périmètre du standard (voir [`CLAUDE.md`](CLAUDE.md)).

## Démarrage

Chaque app fournit un launcher Windows à sa racine :

```
Double-clic sur :  apps\<poc>\start.bat
```

**Seul Python 3.11+ est requis.** Au premier lancement, le script crée
le venv, installe les deps Python et applique les migrations Alembic
(1-3 min). Aux lancements suivants, ~5 secondes : le marker
`.venv\.installed` saute l'install.

Le navigateur s'ouvre tout seul sur `http://127.0.0.1:<port>/` — il
sert l'UI React si `frontend/dist/` a été buildé, sinon la **preview
HTML autonome** (UI vanilla servie par FastAPI, sans Node). `Ctrl+C`
dans la console pour arrêter.

> Pour obtenir l'UI React complète, build le frontend Vite
> (`pnpm install && pnpm build` dans `apps/<poc>/frontend/`, nécessite
> Node 20). Le backend détecte automatiquement `frontend/dist/`.

## Partage à un collègue

Chaque app fournit un packager à sa racine :

```
Double-clic sur :  apps\<poc>\package.bat
```

Il produit `apps/<poc>/dist/<poc>-vX.Y.Z-YYYYMMDD.zip` : un ZIP
autonome (sources de l'app + design-tokens + Python 3.11 embarqué) que
le collègue décompresse et lance via `start.bat`, sans aucun prérequis.

## Structure

```
.
├── apps/                       # 1 dossier = 1 POC autonome
│   ├── _template/              # squelette canonique — copie pour chaque nouveau POC
│   ├── ftm/                    # POC FTM Agent v2
│   ├── pdf-reviewer/           # POC PDF Reviewer
│   ├── doc-writer/             # POC Doc Writer
│   └── ocr-vision/             # POC OCR Vision
│       ├── start.bat + _run.bat        # lancement local (wrapper + logique)
│       ├── package.bat + _package.bat  # génération du ZIP partageable
│       ├── start.sh                    # lanceur Unix
│       ├── backend/                    # FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic
│       └── frontend/                   # React 18 + Vite + TS strict
├── packages/
│   └── ui/                     # @internal/ui — composants partagés (Radix + shadcn)
├── design-tokens/              # tokens.json (dual-theme dark/light) + preset Tailwind
├── docs/
│   └── adr/                    # Architecture Decision Records
├── scripts/                    # check_standard.sh + package_<poc>.py (un par app)
├── tools/                      # binaires optionnels (ex. installeur Python silencieux)
├── legacy/
│   └── ftm-v1/                 # code FTM v1 — lecture seule
├── STANDARD_POC.md             # référence technique du standard
├── CLAUDE.md                   # règles non-négociables (lu par Claude Code)
├── PROMPT_AUDIT_STANDARD.md    # prompt d'audit d'un POC contre le standard
├── package.json                # workspace pnpm racine — scripts dev:<poc>
├── pnpm-workspace.yaml
└── tsconfig.base.json
```

> **Chaque POC est indépendant** : aucune dépendance runtime entre
> `apps/<poc-a>/` et `apps/<poc-b>/`. Le partage se fait uniquement via
> `packages/ui/` et `design-tokens/`.

## Développement frontend (optionnel, nécessite Node 20 + pnpm)

```bash
pnpm install
pnpm dev:ftm            # backend uvicorn + frontend Vite (HMR) en parallèle
pnpm dev:pdf-reviewer   # idem sur port 8001
pnpm dev:doc-writer     # idem sur port 8002
pnpm dev:ocr-vision     # idem sur port 8003
```

## Observabilité

- Logs backend : `structlog` JSON, niveau via `LOG_LEVEL`.
- Health check : `GET /api/v1/health` → `{status, db, llm, version}`.
- Format d'erreur unifié : `{code, message, detail, request_id}`
  (voir [`docs/adr/0003-error-format.md`](docs/adr/0003-error-format.md)).

## Sécurité

- Auth = palier 1 : local seul, bind `127.0.0.1`, jamais `0.0.0.0`.
- CORS en liste blanche (`CORS_ORIGINS`), **jamais `["*"]`**.
- Uploads : taille max + MIME validés côté serveur.
- Secrets uniquement via `.env` (jamais committés). `.env.example` à jour.
- `debug=True` interdit hors dev local.

## Legacy

Le code FTM v1 reste à `legacy/ftm-v1/` en **lecture seule**. Les
hotfixes sécurité appliqués au démarrage du monorepo sont documentés
dans [`legacy/ftm-v1/HOTFIX.md`](legacy/ftm-v1/HOTFIX.md).

## Conformité

Avant chaque commit :

```bash
bash scripts/check_standard.sh
```

Vérifie 13 contraintes — 7 structurelles (préfixe `/api/v1/`, absence
de `console.log` / `print()` / hex en dur / `alert` / `confirm` /
`debug=True`, et variable `PORT` + bascule auto dans chaque `_run.bat`)
+ 6 d'instanciation qui rattrapent les copier-coller incomplets depuis
`apps/_template/` (nom `pyproject.toml`, README réécrit, DB renommée,
section `## Auth`, scripts racine wirés, bind `127.0.0.1`). Voir
[`STANDARD_POC.md`](STANDARD_POC.md#8-tests) pour le détail de chaque règle.

## Créer un nouveau POC

```bash
bash scripts/new_poc.sh <slug> [<port>]
```

Le script copie `apps/_template/` → `apps/<slug>/`, substitue les ~15
marqueurs `TEMPLATE` / `8000` dans tous les fichiers, génère
`scripts/package_<slug>.py`, wire les scripts `dev:<slug>` /
`test:e2e:<slug>` / `openapi:gen:<slug>` dans `package.json`, et
exécute `check_standard.sh` pour valider. Voir
[`STANDARD_POC.md` §11](STANDARD_POC.md#11-ajout-dun-nouveau-poc) pour
la procédure manuelle de fallback.

Toute exception au standard doit être documentée dans la section
« Écarts au standard » du README de l'app concernée.
