# CATI — retranscription PDF plan de montage → template Excel

Automatise la retranscription d'une **nomenclature (BOM)** depuis un **PDF plan de
montage** (format CATI fournisseur, ex. ALSTOM) vers un **template Excel fixe**
(feuille `Catalogue`). Input = PDF ; output = classeur `.xlsx` rempli, prêt à
l'emploi.

Conforme à [`STANDARD_POC.md`](../../STANDARD_POC.md). Bootstrap depuis
[`apps/_template`](../_template/).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification. Le
déploiement (palier 2/3) sort du périmètre POC.

## Workflow

1. **Import** — upload d'un PDF plan de montage. Validation (type, taille),
   déduplication SHA-256, puis **extraction déterministe** du tableau.
2. **Extraction** — PyMuPDF `find_tables` détecte la grille ; les **3 sous-lignes
   Client / Interne / Fournisseur** de chaque article sont **regroupées** par
   `FIG REP` en une ligne logique. Filet **LLM Mistral** optionnel si le
   déterministe échoue (désactivable, fallback gracieux — jamais de 5xx).
3. **Tableau** — revue/correction des lignes extraites + saisie des
   **métadonnées document** (code module, fournisseur, top-assembly, illustration)
   qui ne figurent pas dans le PDF.
4. **Export** — remplissage du template `Catalogue.xlsx` (openpyxl) : une ligne
   par article, bloc en-tête module, **feuille `Suivi` et ligne d'en-tête
   préservées**. Les quantités numériques pures sont écrites en nombre, les
   quantités avec unité (`0.5 kg`) restent du texte.

## Mapping PDF → colonnes Excel (feuille `Catalogue`)

| Colonne | Clé technique | Source |
|---|---|---|
| C | `fig` | FIG REP (ex. `10A`) |
| D | `figreflink` | partie numérique du FIG REP |
| E | `aplomb` | points d'indentation de la désignation |
| F | `description` | désignation (sans les points) |
| J | `bt001_part_no` | référence **Interne** |
| K | `sncf_partno` | référence **Client** |
| L | `pn_supplier` | référence **Fournisseur** |
| N | `qty_assy` | QUANTITE (ES) |
| A, B, M, T | `module`, `partid`, `otan_supplier`, `drw` | métadonnées document |

Le mapping est **structurel** : les valeurs document-level viennent du formulaire
de métadonnées, jamais codées en dur.

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| Extraction PDF | PyMuPDF (`find_tables`) |
| Écriture Excel | openpyxl (template fixe préservé) |
| LLM | Mistral via `httpx` async (pas de SDK), filet optionnel désactivable |
| Frontend | React 18 + TS + Vite + Tailwind + RHF + Zod + i18next + Zustand + TanStack Query |
| UI | `@internal/ui` exclusivement |
| Persistance | SQLite (`backend/data/cati.db`), Alembic dès J1 |

## Endpoints métier (préfixe `/api/v1`)

- `POST /documents` (multipart `files`) — upload PDF + extraction.
- `GET /documents` · `GET /documents/{id}` · `DELETE /documents/{id}`.
- `GET /documents/{id}/items` — lignes extraites.
- `POST /documents/{id}/extract?refresh=true` — ré-extraction.
- `PUT /documents/{id}/header-meta` — métadonnées document.
- `PATCH|POST|DELETE /documents/{id}/items[/{item_id}]` · `POST …/items/reorder`.
- `GET /documents/{id}/export.xlsx` — template Catalogue rempli.

Endpoints standards : `GET /health`, `GET/POST /settings`, `POST /settings/test`,
`GET /admin/stats`, `POST /admin/reset/{documents,all}`.

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Le backend écoute
sur http://127.0.0.1:8007/ et sert l'UI React buildée.

Frontend en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:cati
```

Tests backend :

```bash
cd apps/cati/backend && .venv/Scripts/python -m pytest -q
```

## Écarts au standard

Aucun.
