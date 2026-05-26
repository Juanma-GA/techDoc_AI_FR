# doc-writer

POC de **génération de contenu RAG** : à partir d'un prompt utilisateur et de documents uploadés (PDF, DOCX, PPTX, XLSX, TXT, MD), le modèle Mistral produit un contenu rédactionnel structuré (markdown + citations) en streaming. Export possible en `.md`, `.docx`, `.pdf`, ou `.pptx` via remplissage d'un template à placeholders.

Conforme à [`STANDARD_POC.md`](../../STANDARD_POC.md). Bootstrap depuis [`apps/_template`](../_template/).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| LLM | Mistral via `httpx` async + `sse-starlette` (pas de SDK) |
| Frontend | React 18 + TS + Vite + Tailwind + RHF + Zod + i18next + Zustand + TanStack Query |
| UI | `@internal/ui` exclusivement |
| Persistance | SQLite par défaut (`backend/data/doc-writer.db`), Alembic dès J1 |

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Le script :

1. Détecte Python 3.11+
2. Crée le venv `backend/.venv/`
3. Installe les deps Python (avec `PyMuPDF`, `python-docx`, `python-pptx`, `openpyxl`, `numpy`)
4. Applique les migrations Alembic
5. Lance uvicorn sur `http://127.0.0.1:8002/`

Pour le frontend en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:doc-writer
```

## Fonctionnalités

- **Documents** — upload multi-fichiers, parsing automatique (PDF/DOCX/PPTX/XLSX/TXT/MD), chunking + embeddings Mistral indexés en SQLite (BLOB numpy)
- **Génération** — prompt rédactionnel + sélection de documents (scope) → recherche RAG (cosine similarity) → streaming SSE de la réponse markdown avec citations `[filename]`
- **Sessions** — historique persisté multi-tours (la même session permet d'itérer sur le prompt)
- **Export** — `.md` brut, `.docx` (python-docx), `.pdf` (reportlab), `.pptx` (remplissage de template, cf. ci-dessous)
- **Paramètres** — clé Mistral, base URL, modèles chat/embed configurables via UI (stockés en table `app_config`)

### Export PPTX par remplissage de template

1. Upload un fichier `.pptx` avec `kind=template` (depuis l'onglet Paramètres en mode preview, ou via la zone dédiée du panneau Génération en mode React).
2. Le template doit contenir des marqueurs `{{cle}}` dans le texte des shapes, cellules de tables ou notes du présentateur. Exemple : `# {{titre}}`, `{{conclusion}}`.
3. Au moment de la génération, attache le template à la session (champ `template_doc_id`).
4. Après génération, clique **Télécharger en .pptx** : le backend appelle Mistral en mode JSON pour mapper chaque placeholder au contenu pertinent extrait du markdown généré, puis remplit le template (style du 1er run préservé, sauts de ligne `\n` convertis en `<a:br/>`).
5. Les clés non trouvées par le modèle sont laissées telles quelles (`{{cle}}`).

**Limites** : pas d'injection d'images/charts dynamiques ; un placeholder mixant gras+italique dans la même shape perd la mise en forme intra-placeholder (le style du 1er run prime). Format binaire `.ppt` (Office 97-2003) non supporté.

## Écarts au standard

Aucun.

## Tests

```bash
# Backend
cd backend && pytest

# Frontend (Vitest unitaire)
pnpm --filter @apps/doc-writer-frontend test

# E2E Playwright
pnpm --filter @apps/doc-writer-frontend test:e2e
```

Conformité :

```bash
bash scripts/check_standard.sh
```
