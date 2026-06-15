# ftm

Agent de **F**ormalisation et de **T**ranscription **M**étier — application interne d'analyse documentaire (DOCX/XLSM/PDF), détection d'anomalies selon des règles métier configurables, dashboard et chat assisté par Mistral.

## Auth

**Palier** : 1 — local seul, bind 127.0.0.1, pas d'authentification.

POC local-first stricte conforme à [`STANDARD_POC.md §3.5`](../../STANDARD_POC.md). Aucun déploiement dans le périmètre du standard.

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix).

Le script détecte Python 3.11+, crée le venv, installe les deps, applique les migrations Alembic et lance le backend sur `http://127.0.0.1:8000/`.

Pour lancer le frontend en mode dev (port 5173) :

```bash
pnpm install                                  # depuis la racine du monorepo
pnpm dev:ftm                               # backend + frontend en parallèle
```

## Structure

```
apps/ftm/
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

## UI livrée à l'IT : `preview.html` (et non React)

L'interface **distribuée et exécutée par l'IT est le `backend/app/templates/preview.html`** (rendu par `app/api/preview.py`), **pas** le frontend React.

- **Garanti côté backend** : `app/main.py::_mount_frontend` sert le `preview.html` **par défaut**, et ne sert le SPA React **que** si `FTM_SERVE_SPA=1` ET qu'un `frontend/dist/` existe. Ainsi un **déploiement depuis le repo** (clone `main` + lancement) montre l'app **complète** — 7 onglets, Vue Rédacteur incluse — **que le front soit buildé ou non**. (Sans ça, un déploiement qui lance `pnpm build` génère un `frontend/dist/` et sert la coquille React vide.)
- `scripts/package_ftm.py` n'embarque pas non plus le build React (`frontend/dist`) par défaut — cohérent pour la voie ZIP.
- **Pourquoi** : le front React (`frontend/src/routes/*`) n'est aujourd'hui qu'une **coquille** (pages `common.empty`, aucun appel API) ; toute l'app fonctionnelle vit dans le `preview.html`. Servir le `dist` faisait voir une **app vide** à l'IT (symptôme observé : 4 onglets, pas de Vue Rédacteur). De plus, l'environnement IT n'a pas de Node sanctionné → une UI **sans Node** est la plus stable à supporter.
- **Compromis assumé** : le `preview.html` est un fichier vanilla JS unique (~2300 lignes), donc moins maintenable/évolutif qu'une vraie app React (pas de composants, pas de typage TS, pas de tests UI). Acceptable pour un POC ; à revoir si l'app doit être pérennisée.
- **Réactiver React** (une fois à parité fonctionnelle avec le preview) : lancer le backend avec `FTM_SERVE_SPA=1` et un `frontend/dist/` présent (ou packager avec `python scripts/package_ftm.py --build-frontend`).
- Un test verrouille ce comportement : `backend/tests/test_preview_served.py` (la racine sert le preview complet par défaut).

## Documents de travail métier

`regles-metier-pour-validation.docx` à la racine de l'app est un document de travail synchronisé avec les experts métier. Il sert de source de vérité hors-code pour les règles de validation embarquées dans `backend/app/checks/`. Il est commit pour rester aligné entre l'équipe technique et les experts ; il n'est pas chargé au runtime (les règles vivent dans `backend/data/rules.json` ou les défauts en dur de `app/core/rules.py`).

## Écarts au standard

### 2026-06-10 — UI livrée = `preview.html` (fallback) au lieu du front React
**Règle visée** : règle #13 / standard preview — le `preview.html` est conçu comme *fallback HTML autonome sans Node*, l'UI primaire étant React (règle #1/#3).
**Justification** : le front React n'est qu'une coquille non implémentée ; le `preview.html` porte l'app complète et fonctionnelle. L'IT qui exécute l'app n'a pas de Node sanctionné → une UI sans Node est la plus stable à supporter. Embarquer le build React livrait une app vide à l'IT.
**Plan de retour à la conformité** : implémenter le front React à parité fonctionnelle avec le `preview.html`, puis repackager avec `python scripts/package_ftm.py --build-frontend`. Tant que la parité n'est pas atteinte, le `preview.html` reste l'UI livrée.
**Validation** : à compléter — porteur du POC.

### 2026-06-15 — Ajout d'une CI GitHub Actions
**Règle violée** : posture local-first stricte (`CLAUDE.md`) — « pas de CI » dans le périmètre du standard.
**Justification** : l'app est passée en palier 2/3 (déploiement réel par l'IT depuis `main`). Une CI (`.github/workflows/ci.yml`, périmètre ftm : pytest + `check_standard.sh`) garde `main` saine avant déploiement. CI seule, pas de CD/déploiement auto.
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
