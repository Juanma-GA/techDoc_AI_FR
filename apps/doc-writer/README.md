# doc-writer

POC de **génération de contenu RAG** : à partir d'un prompt utilisateur et de documents uploadés (PDF, DOCX, PPTX, XLSX, TXT, MD), le modèle Mistral produit un contenu rédactionnel structuré (markdown + citations) en streaming. Export possible en `.md`, `.docx`, `.pdf`, ou par **remplissage d'un template** (`.pptx`, `.docx` ou `.pdf`) qui reprend la structure **et la mise en page** d'origine.

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
3. Installe les deps Python (avec `PyMuPDF`, `python-docx`, `python-pptx`, `pdf2docx`, `openpyxl`, `numpy`)
4. Applique les migrations Alembic
5. Lance uvicorn sur `http://127.0.0.1:8002/`

Pour le frontend en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:doc-writer
```

## Fonctionnalités

- **Documents** — upload multi-fichiers, parsing automatique (PDF/DOCX/PPTX/XLSX/TXT/MD), chunking + embeddings Mistral indexés en SQLite (BLOB numpy). Les **PDF scannés** (sans couche texte) passent par un **repli OCR** Tesseract (cf. ci-dessous)
- **Génération** — prompt rédactionnel + sélection de documents (scope) → recherche RAG (cosine similarity) → streaming SSE de la réponse markdown avec citations `[filename]`. **Sans source sélectionnée**, on ne fait **aucun RAG** (on n'injecte pas d'extraits d'autres documents indexés) : la génération s'appuie **uniquement sur le prompt** (prompt système « freeform », sans citations ni contrainte d'extraits)
- **Sessions** — historique persisté multi-tours (la même session permet d'itérer sur le prompt)
- **Export** — `.md` brut, `.docx` (python-docx) / `.pdf` (reportlab) génériques, ou **remplissage d'un template** `.pptx` / `.docx` / `.pdf` qui conserve la mise en page d'origine (cf. ci-dessous)
- **Paramètres** — clé Mistral, base URL, modèles chat/embed configurables via UI (stockés en table `app_config`)

### Export PPTX par remplissage de template

1. Upload un fichier `.pptx` avec `kind=template` (depuis l'onglet Paramètres en mode preview, ou via la zone dédiée du panneau Génération en mode React).
2. Le template doit contenir des marqueurs `{{cle}}` dans le texte des shapes, cellules de tables ou notes du présentateur. Exemple : `# {{titre}}`, `{{conclusion}}`.
3. Au moment de la génération, attache le template à la session (champ `template_doc_id`).
4. Après génération, clique **Télécharger en .pptx** : le backend appelle Mistral en mode JSON pour mapper chaque placeholder au contenu pertinent extrait du markdown généré, puis remplit le template (style du 1er run préservé, sauts de ligne `\n` convertis en `<a:br/>`).
5. Les clés non trouvées par le modèle sont laissées telles quelles (`{{cle}}`).

**Limites** : pas d'injection d'images/charts dynamiques ; un placeholder mixant gras+italique dans la même shape perd la mise en forme intra-placeholder (le style du 1er run prime). Format binaire `.ppt` (Office 97-2003) non supporté.

### Remplissage de template Word (`.docx`) et PDF (`.pdf`)

Même mécanique que le PPTX, via un moteur dédié ([`core/docx_template.py`](backend/app/core/docx_template.py)), choisi automatiquement par le dispatcher [`core/template_format.py`](backend/app/core/template_format.py) :

1. Upload un `.docx` ou un `.pdf` avec `kind=template`.
2. Détection des zones : marqueurs `{{cle}}` / `XXX` (remplis **dans le run du marqueur** → la police/couleur/taille du marqueur sont conservées), plus les cadres à remplir (cellules de tables, paragraphes vides sous un titre).
3. Export : quand un template Word/PDF est attaché, **les boutons `.docx` ET `.pdf` remplissent le template** et produisent un **`.docx`** (le backend **remplit le template d'origine en place**). Sections, en-têtes/pieds, styles, polices, tableaux et images du gabarit sont donc **conservés nativement** — seul le texte des zones change. Le bouton `.pdf` redirige vers ce remplissage (le rendu markdown→pdf générique ne serait pas fidèle au template) : il n'existe **pas de re-rendu PDF fidèle** côté local (cela demanderait LibreOffice/docx2pdf, hors posture local-first). Si tu veux un PDF, exporte le `.docx` rempli puis « Enregistrer au format PDF » depuis Word.
4. **Template PDF** : un PDF n'étant pas éditable, il est d'abord **converti en `.docx` via `pdf2docx`** (sidecar caché sur disque, conversion unique et paresseuse), puis traité comme un template Word. La fidélité dépend de la propreté du PDF source (un PDF scanné/image sans texte échoue avec un message explicite).
5. **Zones automatiques** : pour Word/PDF, les zones sont détectées et **auto-validées** (aucune étape manuelle requise) tant que le template contient des emplacements à remplir. Un template de **prose sans aucun emplacement** (pas de `{{…}}`, `XXX`, tableau ni paragraphe vide) renvoie `NO_ZONES_FOUND` : il n'y a rien où injecter sans réécrire le document (ce qui perdrait la mise en page).

### Lecture des PDF (vision / OCR)

Le parser PDF ([`backend/app/parsers/pdf_parser.py`](backend/app/parsers/pdf_parser.py)) lit les PDF en **cascade** (chaque niveau ne s'active que si le précédent échoue) :

0. **Couche texte native** — si le PDF a une couche texte exploitable (PDF éditable, CV avec texte sélectionnable) : utilisée directement, instantanée et gratuite. Ni vision ni OCR.
1. **Vision (multimodal)** — quand la couche texte manque (PDF **image** / scan / CV graphique) et qu'une clé Mistral est configurée : chaque page est rendue en image et interprétée par un modèle vision Mistral, qui lit **aussi le graphique** (drapeaux → langue, barres/points/jauges → niveau) que l'OCR texte ne comprend pas. Réglable dans **Paramètres** (`vision_model`, défaut `mistral-small-latest`). Plafonné à 10 pages (au-delà → niveau 2).
2. **OCR document** (`/v1/ocr`) — repli si la vision échoue : texte + structure (colonnes, tableaux). Réglable (`ocr_model`, défaut `mistral-ocr-latest`).
3. **Extraction LOCALE** — repli final : couche texte PyMuPDF + OCR Tesseract (`get_textpage_ocr`) sur les pages sans texte.

> Le texte est extrait **une fois, à l'upload**, et mis en cache (`Document.extracted_text`). Après un changement de moteur OCR, **re-uploader** un document existant pour le ré-extraire.

- **Confidentialité** : vision/OCR envoient le document (images ou PDF) à l'API Mistral — même posture que le reste du POC (le texte des sources part déjà chez Mistral). Mistral est le seul fournisseur autorisé. Pas de stockage tiers.
- **Repli Tesseract configurable** (env / `.env`) : `pdf_ocr_enabled` (défaut `true`), `pdf_ocr_lang` (`fra+eng`), `pdf_ocr_dpi` (`300`), `pdf_ocr_tessdata`.
- **Installer Tesseract (Windows, optionnel)** : `winget install UB-Mannheim.TesseractOCR`, puis `tesseract.exe` au PATH et si besoin `TESSDATA_PREFIX` vers `tessdata` (packs `fra` + `eng`). Inutile tant que la vision/l'OCR Mistral sont disponibles.

## Écarts au standard

- **Dépendance `pdf2docx`** (règle #1 — toute dépendance hors stack imposée se justifie ici) : nécessaire pour accepter un **PDF comme template** (conversion PDF → Word avant remplissage). Tire `opencv-python-headless` et `fonttools`. Aucune alternative dans la stack imposée ne permet de re-remplir un PDF en conservant sa mise en page. Périmètre local-first : la dépendance reste côté backend POC, non exposée.
- **Dépendance système Tesseract** (binaire externe, hors pip) : nécessaire pour l'**OCR des PDF scannés** chargés comme source. PyMuPDF (déjà imposé) l'utilise via `get_textpage_ocr`, donc **aucune dépendance pip ajoutée**. Optionnelle : sans Tesseract, seuls les PDF avec couche texte sont indexés (dégradation gracieuse). À installer manuellement par le dev (cf. ci-dessus).

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

## Écart au standard assumé — skin pixel-identique au preview

À la demande explicite de l'utilisateur, l'app **React** doit être **visuellement
identique** au `preview.html` (qui sert de spécification UI). Pour garantir cette
identité, les pages/composants React réutilisent le **CSS sur-mesure du preview**
(`frontend/src/styles/preview-skin.css` : classes `.card` / `.btn` / `.nav-item` /
`.kpi` / `.switch` / `.data-table` / `.modal-*` / `.slide-*` …) **au lieu** des
composants `@internal/ui`.

C'est un **écart documenté** aux règles non-négociables **#3** (« composants UI
uniquement via `@internal/ui` ») et **#4** (« tokens via le preset Tailwind ») de
[`STANDARD_POC.md`](../../STANDARD_POC.md) :

- Les **variables de couleur** restent dérivées de `design-tokens/tokens.json`
  (générées dans `preview-skin.css`, `:root` clair / `.dark` sombre), donc le
  dual-theme et la palette du standard sont préservés.
- `@internal/ui` n'est plus consommé par ce POC (les composants orphelins
  `TemplatePanel` / `ZoneList` / `TemplateZonesCard` ont été supprimés).
- Build front : `vite build` (le `tsc -b` du script `build` échoue au niveau repo,
  TS6310 ; le typecheck applicatif se fait via un `tsconfig` sans `references`).
