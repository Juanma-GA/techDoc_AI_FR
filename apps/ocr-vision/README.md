# ocr-vision

POC d'**OCR + reconnaissance visuelle** sur des documents techniques :
à partir d'une image (PNG/JPG) ou d'un PDF, le backend envoie le fichier
aux modèles Mistral (`/v1/ocr` + modèle multimodal) et renvoie en
parallèle :

- le **texte transcrit** par l'OCR,
- une **description en français** du contenu visible (objets,
  équipements, schémas, pictogrammes, texte visible).

OCR et reconnaissance sont indépendants : si l'un échoue, l'autre peut
quand même remonter.

Conforme à [`STANDARD_POC.md`](../../STANDARD_POC.md). Bootstrap depuis
[`apps/_template`](../_template/).

## État actuel du POC

Deux briques :

1. **OCR / reconnaissance** (`POST /api/v1/vision/test`) — validation de la
   chaîne OCR + multimodal Mistral, sans persistance.
2. **Capitalisation des données extraites** — OCRiser des PDF puis remplir
   une **table définie** (colonnes + règles d'extraction), capitaliser par
   **projet**, et **exporter en CSV** dans un répertoire cible. Voir la
   section [Capitalisation](#capitalisation-des-données-extraites).

## Capitalisation des données extraites

Workflow : **OCRiser un PDF → remplir une table (N lignes) → exporter en CSV**.

- **`TableTemplate`** : définition **réutilisable** d'une table — nom +
  colonnes `[{key, label, type, rule}]`, `type ∈ text|number|date|bool`,
  `rule` = consigne d'extraction par colonne.
- **`Project`** : unité de capitalisation.
- **`ProjectTable`** : un template appliqué à un projet ; fige un **snapshot**
  des colonnes et porte les lignes extraites. C'est « la table » exportée.
- **`ExtractedRow`** : une ligne extraite (`values` = `{key: value}`).

Routes : `POST /api/v1/extract` (upload + `project_table_id` → OCR puis
extraction structurée LLM → N lignes persistées) et `POST /api/v1/export`
(`project_table_id` + `target_dir` + `format` ∈ `csv`|`xlsx` → écrit
`<projet>__<table>.<ext>`). L'extraction respecte l'interrupteur `llm_enabled`
(OFF → 200 + 0 ligne).

**Images / illustrations** : lors d'un `/extract` sur un **PDF**, les images du
document sont aussi extraites (PyMuPDF, façon s1000d-extractor : `page.get_images`
→ JPG, CMYK/alpha→RGB) et stockées dans `backend/data/storage/<project_table_id>/`
(gitignoré). Table `ExtractedImage`. Routes `GET /project-tables/{id}/images`
(liste), `GET /images/{id}/file` (service JPG), `DELETE /images/{id}`, et
`POST /images/export` (`project_table_id` + `target_dir` → copie les JPG dans un
sous-dossier `<projet>__<table>_images/` du répertoire cible). Best-effort :
image/DOCX/OCR ou PDF sans image → 0 image, jamais d'erreur. Galerie de vignettes
téléchargeables dans l'onglet Extraction, avec export vers un répertoire dédié.

**Colonne « Clé »** : identifiant technique de colonne (minuscules, sans espace ni
accent, ex. `part_number`) — nom de colonne dans le CSV/XLSX et cible des règles.
Distincte du **Libellé** (en-tête lisible). La clé est auto-suggérée depuis le
libellé, puis modifiable.

**Sortie XLSX** : en plus du CSV (`;` + UTF-8-sig), export `.xlsx` via `openpyxl`
(en-têtes = libellés). Sélecteur de format dans l'onglet Extraction.

### Écart documenté au standard — export CSV sur disque

`POST /api/v1/export` écrit un fichier CSV sur un **chemin disque local
arbitraire** fourni par l'utilisateur. C'est un **écart assumé** au cadre
« pas d'accès disque hors périmètre app », justifié par la posture
**local-first strict** (palier 1, bind `127.0.0.1`, un seul utilisateur sur
son PC). Garde-fous : le dossier cible doit **exister**, le nom de fichier
est **assaini** (`[^A-Za-z0-9_.-]` → `_`) et un contrôle anti-traversée
vérifie que la sortie reste dans le dossier cible. CSV en **UTF-8-sig +
séparateur `;`** (ouverture directe dans Excel FR). En cas de déploiement
palier 2/3 (bind exposé), cet endpoint devra être revu (répertoire
whitelisté ou download navigateur).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| LLM | Mistral via `httpx` async (OCR `/v1/ocr` + modèle multimodal), pas de SDK |
| Frontend | React 18 + TS + Vite + Tailwind + RHF + Zod + i18next + Zustand + TanStack Query |
| UI | `@internal/ui` exclusivement |
| Persistance | SQLite par défaut (`backend/data/ocr-vision.db`), Alembic dès J1 |

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Le script :

1. Détecte Python 3.11+
2. Crée le venv `backend/.venv/`
3. Installe les deps Python
4. Applique les migrations Alembic
5. Lance uvicorn sur `http://127.0.0.1:8003/`

Pour le frontend en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:ocr-vision
```

## Endpoint métier

`POST /api/v1/vision/test` — multipart/form-data

| Champ | Type | Description |
|---|---|---|
| `file` | file (image/* ou application/pdf) | Le document à analyser |
| `prompt` | string (optionnel) | Prompt custom pour la reconnaissance visuelle (par défaut : description FR en 3-5 phrases) |

Réponse :

```json
{
  "ocr_text": "...",
  "description": "...",
  "errors": []
}
```

`errors` liste les erreurs partielles (ex. OCR a échoué mais description OK).

La clé Mistral est lue depuis la table `app_config` (configurable via
l'onglet **Paramètres** du preview ou via `POST /api/v1/settings`).

## Écarts au standard

Aucun.

## Tests

```bash
# Backend
cd backend && pytest

# Frontend (Vitest unitaire)
pnpm --filter @apps/ocr-vision-frontend test

# E2E Playwright
pnpm --filter @apps/ocr-vision-frontend test:e2e
```

Conformité :

```bash
bash scripts/check_standard.sh
```
