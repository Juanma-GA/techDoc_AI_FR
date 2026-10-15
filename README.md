# Internal POC Monorepo

Monorepo interne hébergeant plusieurs POC IA full-stack (FastAPI + React),
développés dans un **tronc commun partagé** (`packages/ui`, `design-tokens/`,
scripts, standard) et conformes à [`STANDARD_POC.md`](STANDARD_POC.md).
Chaque app est indépendante côté runtime mais s'aligne sur les mêmes
règles, les mêmes composants UI et les mêmes tokens.

Voir [`docs/index.md`](docs/index.md) pour la hiérarchie documentaire et
[`docs/apps/README.md`](docs/apps/README.md) pour l'inventaire canonique.

| App | Rôle | Port par défaut cible |
|---|---|---|
| [`apps/corpus-agent/`](apps/corpus-agent/) | Analyse de corpus et de fiches de tâches de maintenance | 8001 |
| [`apps/doc-writer/`](apps/doc-writer/) | Génération de contenu rédactionnel en RAG streaming | 8002 |
| [`apps/doc-reviewer/`](apps/doc-reviewer/) | Révision d'anomalies dans des documents techniques | 8003 |
| [`apps/catia-toolbox/`](apps/catia-toolbox/) | Outils de traitement documentaire CATIA | 8004 |
| [`apps/ocr-vision/`](apps/ocr-vision/) | OCR et extraction visuelle sur documents techniques | 8005 |
| [`apps/s1000d-extractor/`](apps/s1000d-extractor/) | Extraction et transformation S1000D | 8006 |
| [`apps/brdp-manager/`](apps/brdp-manager/) | Gestion de BRDP | 8007 |
| [`apps/xml-proofreader/`](apps/xml-proofreader/) | Relecture et correction XML | 8008 |
| [`apps/image-replace/`](apps/image-replace/) | Détection et remplacement local de texte dans les images (PaddleOCR + LaMa, à intégrer) | 8010 |
| [`apps/_template/`](apps/_template/) | Squelette canonique à copier pour démarrer un nouveau POC | — |

Le launcher tente le port par défaut puis utilise le premier port libre
suivant. Les différences actuelles entre launchers sont recensées dans
[`docs/apps/README.md`](docs/apps/README.md) et seront corrigées séparément.

> **Principe directeur** : ces apps sont des **POC local-first stricts**
> — ils tournent localement sur le PC du dev. Pas de Docker, pas de CI,
> pas de déploiement dans le périmètre du standard (voir [`CLAUDE.md`](CLAUDE.md)).

## Démarrage

Chaque app fournit un launcher Windows à sa racine :

```
Double-clic sur :  apps\<poc>\start.bat
```

**Python 3.11+ et Node 20 + pnpm sont requis pour construire l'UI React.**
Le package partageable contient le bundle React validé ; l'utilisateur final
n'a pas besoin de Node pour l'exécuter. Au premier lancement, le script crée
le venv, installe les deps Python et applique les migrations Alembic.

Le navigateur s'ouvre tout seul sur `http://127.0.0.1:<port>/` et sert
l'UI React buildée depuis `frontend/dist/`. Si le bundle est absent, le
lanceur signale l'erreur de build au lieu de servir une seconde UI.
`Ctrl+C` dans la console pour arrêter.

> En développement, build le frontend Vite avec `pnpm build` dans
> `apps/<poc>/frontend/`. Le packaging doit inclure un `frontend/dist/`
> valide avant distribution.

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
│   └── <poc>/                  # voir docs/apps/README.md pour la liste complète
│       ├── start.bat + _run.bat        # lancement local (wrapper + logique)
│       ├── package.bat + _package.bat  # génération du ZIP partageable
│       ├── start.sh                    # lanceur Unix
│       ├── backend/                    # FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic
│       └── frontend/                   # React 18 + Vite + TS strict
├── packages/
│   └── ui/                     # @internal/ui — composants partagés (Radix + shadcn)
├── design-tokens/              # tokens.json (dual-theme dark/light) + preset Tailwind
├── docs/
│   ├── index.md                # index et hiérarchie documentaire
│   ├── apps/                   # inventaire et onboarding des apps
│   ├── standards/              # modèles et contrats partagés
│   ├── history/                # rapports datés non normatifs
│   └── adr/                    # Architecture Decision Records
├── scripts/                    # check_standard.sh + package_<poc>.py (un par app)
├── tools/                      # binaires optionnels (ex. installeur Python silencieux)
├── STANDARD_POC.md             # référence technique du standard
├── CLAUDE.md                   # méthode et sécurité locales
├── AGENTS.md                   # point d'entrée de compatibilité des agents
├── CONTRIBUTING.md             # workflow Git, commits et pull requests
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
pnpm dev:<poc>          # backend uvicorn + frontend Vite (HMR) en parallèle
```

Les scripts disponibles sont déclarés dans [`package.json`](package.json).

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

## Conformité

Avant chaque commit :

```bash
bash scripts/check_standard.sh
```

Vérifie 15 contraintes — 7 structurelles, 6 d'instanciation, 1 de
configuration LLM et 1 de robustesse du launcher. Il ne constitue pas une
preuve de conformité AACF.
Les contrôles rattrapent notamment les copier-coller incomplets depuis
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
