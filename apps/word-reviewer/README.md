# Word-Reviewer

Revue de conformité de documents **Word (`.docx`)** contre la norme **ATA100**
et un jeu de **règles client** importé depuis un fichier Excel (checklist
`Topic | Check`). Jumeau du POC `pdf-reviewer`, mais pour le format Word :
détection des non-conformités, suggestions acceptables/éditables, application
des corrections dans le `.docx`, et export du fichier corrigé.

Pensé pour un usage **local d'abord** (un relecteur sur son poste), puis un
partage serveur ultérieur (la base reste portable SQLite ↔ Postgres via Alembic).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, **pas d'authentification**.
Le déploiement serveur (paliers 2/3, multi-utilisateurs) sort du périmètre de
ce POC et devra lever le bind local et ajouter une authentification.

## Démarrage

```bat
apps\word-reviewer\start.bat        REM Windows (one-click)
```

```bash
apps/word-reviewer/start.sh         # Unix
```

Le backend écoute sur `http://127.0.0.1:8006/` (bascule automatique sur le
port libre suivant s'il est occupé). UI servie :
- le SPA React (`frontend/dist/`) s'il a été buildé ;
- sinon le **preview HTML autonome** (vanilla JS, sans Node) servi par le backend.

## Trois niveaux de contrôle

La checklist client mélange des items de natures différentes ; le moteur les
répartit en trois tiers :

- **Déterministe** (regex / structurel / style / zone) — corrigeable
  automatiquement : remplacements de termes, copyright, texte justifié, footer
  normalisé, présence et cohérence des sections, etc.
- **LLM (Mistral)** — règles « molles » en langage naturel (conformité au
  modèle ATA100, phrases standard, orthographe). Vérifiées par un second
  passage adversarial + score de confiance pour limiter les faux positifs.
- **Manuel** — items visuels non automatisables (logo, illustrations, mise en
  page) présentés comme **checklist à cocher** par le relecteur.

## Entrées / sorties

- **Upload** : un `.docx`, plusieurs fichiers, ou un `.zip` (dossier complet,
  `.docx`/`.doc` extraits récursivement). Les documents d'un même upload forment
  un **lot**.
- **`.doc` legacy** : accepté et **converti en `.docx` à l'upload** via LibreOffice
  (`soffice`) si présent, sinon MS Word (automation COM, Windows). Si aucun des
  deux n'est disponible, l'upload renvoie une erreur invitant à enregistrer en
  `.docx`.
  - **Poste où Word bloque l'enregistrement `.docx`** (stratégie Office / Trust
    Center « File Block », fréquent en entreprise) : Word ne peut pas produire le
    `.docx` requis. Utiliser **LibreOffice** (même portable, sans admin) et pointer
    la variable d'env **`WR_SOFFICE_PATH`** vers `soffice.exe` — renseignable dans
    `_run.bat` / `start.sh`. La détection couvre aussi un LibreOffice portable posé
    dans `%LOCALAPPDATA%`, `%USERPROFILE%`, ou `…\Desktop|Downloads\LibreOfficePortable\`.
- **Export** : un `.docx` corrigé, ou un `.zip` quand plusieurs documents sont
  sélectionnés.

## Règles ATA100 + checklist client

- Au démarrage, **seul ATA100** est présent (référentiel par défaut, builtin).
- L'utilisateur **importe sa checklist Excel** (`Topic | Check`) depuis l'onglet
  *Standards & Règles* ; chaque import **remplace** le jeu de règles custom
  (« repartir de 0 »). ATA100 builtin n'est jamais écrasé.

## Stack

Backend FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog ;
`python-docx` (lecture/écriture `.docx` + révisions via lxml), `openpyxl`
(import checklist), Mistral via `httpx` async + SSE. Front React 18 + TS + Vite
+ Tailwind (optionnel ; le preview HTML reste le livrable primaire).

## Endpoints clés

- `GET /api/v1/health`, `GET /api/v1/admin/stats`, `POST /api/v1/admin/reset/all`
- `GET/POST /api/v1/settings` (+ `/settings/test`) — config Mistral runtime
- `POST /api/v1/documents` (upload single/multi/zip), `GET /api/v1/documents/{id}/export`
- `POST /api/v1/documents/{id}/analyze` (SSE), `GET /api/v1/documents/{id}/suggestions`
- `POST /api/v1/rules/import` (checklist Excel, mode remplacement)
- `GET /api/v1/standards`, `GET /api/v1/metrics`

## Tests

```bash
cd apps/word-reviewer/backend && python -m pytest
bash scripts/check_standard.sh
```

Les tests s'appuient sur des fixtures **synthétiques** (`tests/fixtures/`,
`tests/golden/`) — aucune donnée client réelle n'est lue.

## Écarts au standard

- Réutilisation de modules portés depuis `apps/pdf-reviewer` (moteur de règles,
  schémas, routes) adaptés au format `.docx`. Le squelette reste issu de
  `apps/_template` conformément à la règle d'instanciation.
