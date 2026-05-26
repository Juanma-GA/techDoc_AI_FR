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

## Documents de travail métier

`regles-metier-pour-validation.docx` à la racine de l'app est un document de travail synchronisé avec les experts métier. Il sert de source de vérité hors-code pour les règles de validation embarquées dans `backend/app/checks/`. Il est commit pour rester aligné entre l'équipe technique et les experts ; il n'est pas chargé au runtime (les règles vivent dans `backend/data/rules.json` ou les défauts en dur de `app/core/rules.py`).

## Écarts au standard

Aucun pour le moment. Si un écart est introduit, le documenter ici au format :

```markdown
### <date> — <titre court>
**Règle violée** : §<numéro section> — <énoncé court>
**Justification** : <pourquoi>
**Plan de retour à la conformité** : <si applicable>
**Validation** : <mainteneur>
```
