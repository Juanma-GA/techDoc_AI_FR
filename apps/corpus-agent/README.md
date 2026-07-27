# Corpus Agent

**Corpus Agent** — application interne d'analyse documentaire (DOCX/XLSM/PDF) à l'échelle d'un corpus multi-fichiers, détection d'anomalies selon des règles métier configurables, dashboard et chat assisté par Mistral.

## Auth

**Palier** : 1 — local seul, bind 127.0.0.1, pas d'authentification.

POC local-first stricte conforme à [`STANDARD_POC.md §3.5`](../../STANDARD_POC.md). Aucun déploiement dans le périmètre du standard.

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix).

Le script détecte Python 3.11+, crée le venv, installe les deps, applique les migrations Alembic et lance le backend sur `http://127.0.0.1:8000/`.

Pour lancer le frontend en mode dev (port 5173) :

```bash
pnpm install                                  # depuis la racine du monorepo
pnpm dev:corpus-agent                      # backend + frontend en parallèle
```

## Structure

```
apps/corpus-agent/
├── README.md          # ce fichier
├── start.bat          # lanceur Windows
├── start.sh           # lanceur Unix
├── backend/           # FastAPI + SQLite + Alembic + Mistral
│   ├── README.md      # détail tech backend, conventions
│   ├── app/
│   ├── alembic/
│   ├── data/          # SQLite + uploads (gitignoré)
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
└── frontend/          # React 18 + Vite + Tailwind + i18next
    ├── src/
    ├── tests/e2e/
    └── package.json
```

## UI : React (Vite), servie à `/` — React-only (règle #13)

Le **front React** (`frontend/`) est l'**UI unique** (7 onglets, chat SSE). Plus de preview HTML autonome : le `preview.html` et son routeur `api/preview.py` ont été **retirés** (2026-06-19), conformément à la règle #13 (React obligatoire, le build Vite est un pré-requis).

- **Servi par défaut** : `app/main.py::_mount_frontend` sert `frontend/dist/` **dès qu'il existe**. Si le dist est **absent**, `/` renvoie un **503 « frontend non buildé »** (jamais une UI de substitution).
- **Parité visuelle** : le React réutilise le CSS sur-mesure via `frontend/src/styles/preview-skin.css` (classes `.card/.btn/.kpi/.slicer-pill/.red-*`, variables reprises de `design-tokens/tokens.json`) — voir l'écart #4 ci-dessous. Les primitives riches (FileDropzone) viennent de `@internal/ui`.
- **i18n** : le React charge les traductions depuis le backend `GET /api/v1/i18n/{lang}` ; `src/locales/*.json` ne sont qu'un fallback offline minimal.
- **Packaging** : `scripts/package_corpus_agent.py` embarque `frontend/dist/` (build local, ou `--build-frontend` pour le (re)builder). Le dist devient donc **requis** dans le ZIP (sans lui, le recipient obtient un 503).
- **Dev** : `pnpm dev:corpus-agent` (Vite :5173, proxy `/api`→:8000). `apps/corpus-agent/start.bat` lance le backend (:8000) et, si pnpm est dispo, une fenêtre Vite (:5173).

## Corpus par dossier connecté (OneDrive / local)

En plus de l'upload manuel, un projet peut **connecter un dossier local** (typiquement un dossier OneDrive **déjà synchronisé** sur le poste) depuis la carte *Documents*. Le parcours reste **local-first** (règle #8) : aucune auth ni API cloud, on lit les fichiers déjà présents sur le disque.

- `POST /projects/{id}/files/list-folder {path}` — liste (récursif, sans ingérer) pour **sélectionner** les fichiers ; les extensions bloquées sont marquées `blocked`.
- `POST /projects/{id}/files/sync-folder {path, only?}` — ingère la sélection (`only` = chemins relatifs) ou tout le dossier, via la **même** logique que l'upload (`_ingest_file` : dédup nom+hash, parsing, versionning). Un fichier KO (cloud-only non hydraté, illisible) n'interrompt pas le lot. Plafond `_FOLDER_MAX_FILES` = 500.
- `GET`/`DELETE /projects/{id}/corpus-folder` — chemin mémorisé dans `project.corpus_path` (migration `b9c0d1e2f3a4`). La déconnexion oublie le chemin sans supprimer les fichiers déjà ingérés.

## Documents de travail métier

`regles-metier-pour-validation.docx` à la racine de l'app est un document de travail synchronisé avec les experts métier. Il sert de base pour construire la **checklist** de contrôle (import Excel dans Paramètres). Depuis le passage en **checklist-only** (voir écart 2026-07-21), l'app n'embarque plus de règles codées : toutes les règles vivent dans `backend/data/rules.json` (`regles_personnalisees`), alimentées par l'import de checklist ou l'édition Paramètres, et jugées par l'IA (`app/checks/custom_rules.py`).

## Écarts au standard

### 2026-07-21 — Moteur « checklist-only » (suppression des règles déterministes codées)
**Règle visée** : #6 (LLM désactivable avec **fallback gracieux déterministe** — quand OFF, chaque route saute la tâche IA mais renvoie un résultat déterministe).
**Décision** : à la demande du porteur, corpus-agent n'évalue plus **que** via la checklist (règles personnalisées importées / saisies, jugées par l'IA). Les ~27 règles déterministes codées (script, granule, ordre des tâches, doublons rechanges, dimensions/taille illustrations, format de repérage, unités numériques, cross-checks référentiel BF/BH/BJ & BASL…) et les 3 règles IA du catalogue ont été **retirées** : modules `app/checks/{script,granule,text_rules,operations,illustration,referentiel_items}.py`, `app/core/rules_catalog.py`, `app/core/rules_registry.py`, endpoint `GET /settings/rules/catalog`, carte UI « Catalogue de règles ».
**Conséquence assumée** : il n'y a **plus de contrôle déterministe local**. Interrupteur LLM **OFF** (ou clé Mistral absente) ⇒ l'analyse aboutit en **HTTP 200 mais sans aucune anomalie** (au lieu du socle déterministe précédent). Le seul type d'anomalie émis est désormais `personnalisee`.
**Justification** : le métier veut piloter 100 % des contrôles depuis un Excel éditable (aucun redéploiement pour ajouter/modifier une règle) ; les consignes custom peuvent référencer les colonnes du référentiel via les placeholders `{nom}`.
**Plan de retour à la conformité** : réintroduire un socle déterministe minimal (au moins les vérifs structurelles/mesurables qu'un LLM ne peut pas faire de façon fiable) si l'on veut restaurer le fallback de la règle #6.
**Validation** : à compléter — porteur du POC.

### 2026-06-19 — Durcissement sécurité production (chiffrement, anti-injection, rate-limit, bind)
**Règle visée** : #8 (auth = local seul, palier 1, bind `127.0.0.1` obligatoire, jamais `0.0.0.0`) + posture local-first stricte.
**Justification** : l'app est déployée par l'IT (palier 2/3, hors périmètre du standard). Travail de durcissement rapatrié depuis `main`/ftm pour ne pas régresser en sécurité lors de la bascule ftm → corpus-agent :
- `app/core/encryption.py` — chiffrement Fernet de la clé Mistral au repos (`ENCRYPTED_KEYS`), câblé dans `mistral_client.py`. Off par défaut (`ENCRYPTION_KEY` vide = clair, local).
- `app/core/prompt_sanitizer.py` — défense anti-injection, appliquée sur la question dans `api/chat.py`.
- Rate-limiting `slowapi` (`main.py` + `rate_limit_*` dans `config.py`).
- `bind_host`/`bind_port` configurables (`0.0.0.0` en prod via `.env`). Voir [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md).

Tous ces réglages restent **inertes en local** (défauts sûrs : bind `127.0.0.1`, pas d'origine CORS prod, chiffrement off), donc le palier 1 local-first est préservé tant que le `.env` n'est pas surchargé.
**Plan de retour à la conformité** : sans objet tant que l'app est déployée ; si elle redevient un POC local-first jetable, ces réglages restent neutres (défauts) ou peuvent être retirés.
**Validation** : à compléter — porteur du POC.

### 2026-06-17 — React porté à parité 1:1 (résout l'écart « UI = preview »)
**Historique** : tant que le React n'était qu'une coquille, le `preview.html` était l'UI livrée (écart à la règle #1/#3). Le React est désormais à parité 1:1 et redevient l'UI primaire. Écart **résolu**. Le `preview.html`/`api/preview.py` ont ensuite été **supprimés** (2026-06-19) : React-only, plus de fallback HTML.

### 2026-06-17 — Skin CSS du preview réutilisé dans le React (au lieu de `@internal/ui`)
**Règle visée** : #3 (composants via `@internal/ui`) / #4 (tokens design).
**Justification** : pour un rendu **strictement identique** à l'UI historique (parité 1:1 demandée), le React réutilise le CSS sur-mesure (`frontend/src/styles/preview-skin.css`, classes `.card/.btn/.kpi/...`) plutôt que les composants `@internal/ui`. Les variables CSS reprennent `design-tokens/tokens.json`. Les primitives riches (`FileDropzone`) viennent quand même de `@internal/ui`.
**Plan de retour à la conformité** : migrer progressivement les classes skin vers les composants `@internal/ui` si l'app est pérennisée.
**Validation** : à compléter — porteur du POC.

### 2026-06-15 — Ajout d'une CI GitHub Actions
**Règle violée** : posture local-first stricte (`CLAUDE.md`) — « pas de CI » dans le périmètre du standard.
**Justification** : l'app est passée en palier 2/3 (déploiement réel par l'IT depuis `main`). Une CI (`.github/workflows/ci.yml`, périmètre corpus-agent : pytest + `check_standard.sh`) garde `main` saine avant déploiement. CI seule, pas de CD/déploiement auto.
**Plan de retour à la conformité** : sans objet tant que l'app est déployée ; si elle redevient un POC local-first jetable, retirer le workflow.
**Validation** : à compléter — porteur du POC.

Format pour les prochains écarts :

```markdown
### <date> — <titre court>
**Règle violée** : §<numéro section> — <énoncé court>
**Justification** : <pourquoi>
**Plan de retour à la conformité** : <si applicable>
**Validation** : <mainteneur>
```
