# catia-toolbox — Catia Toolbox

POC multi-modules (slug technique `catia-toolbox`, titre affiche
**Catia Toolbox**) qui regroupe plusieurs automatisations CATIA travaillant
toutes sur des **donnees exportees / neutres** (pas de CATIA live requis) et
produisant des **plans relisables** (dry-run) :

1. **Arborescence** — optimisation d'une structure de fichiers desorganisee
   (heuristiques + Mistral) -> plan CSV + script `.bat` / `.sh`.
2. **Comparaison** — detection des pieces ajoutees / supprimees / modifiees
   entre deux imports.
3. **Verifications** — checks configurables (profondeur, nommage, extensions
   interdites, doublons, dossiers vides).
4. **Conversion** — plan CATIA 3D -> Composer : mapping CSV + **script Python
   `win32com` pilotant Composer** (DRY_RUN par defaut, a lancer par l'utilisateur).
5. **Remplacement** — plan de remplacement de pieces a partir d'un mapping
   (CSV/JSON) -> CSV + macro CATIA squelette.
6. **Colorisation** — attribue une couleur RGB aux pieces selon une strategie
   (`by_change` depuis une comparaison, `by_type`, `by_depth`) -> CSV
   `path;r;g;b;raison` + **script Python `win32com` colorisant les acteurs
   Composer** (DRY_RUN) + macro CATIA V5 (`SetRealColor`) + **simulation visuelle**
   (grille de tuiles colorees dans l'UI + export SVG autonome). Couleurs en
   triplets RGB (jamais d'hexadecimal en dur).

**Composer est dans le perimetre** : les scripts Composer sont de vrais scripts
Python `win32com` (executables apres relecture, `DRY_RUN=True` par defaut). Le
backend reste neanmoins plan-only (il genere les scripts, ne pilote pas Composer
lui-meme). Les noms d'API Composer exacts (ProgID, `Open`/`SaveAs`, propriete
couleur) sont parametres en tete de script avec des `TODO` a confirmer selon la
version du SDK Composer.

> **Le POC ne deplace, ne renomme, ne convertit, ne colorise et ne supprime
> JAMAIS de
> fichier.** Il produit des plans ; l'utilisateur relit les scripts et les
> execute lui-meme. Aucune commande `del` / `rm` n'est generee.

Tous les modules partagent un meme **import** (scan de dossier en metadonnees
seules, ou listing CSV/JSON).

## Pipeline production Lot 3 (5 etapes)

L'UI regroupe les modules selon les 5 etapes du process CATComposer, chacune
validable independamment :

| Etape | Role | Outils |
|---|---|---|
| **1. Identification** | Lire la nomenclature `.xlsm` + les DE `.zip` -> CATPart a traiter (+ SIN mono-couleur) | `identification` (nouveau), `import` (Source), `diff` |
| **2. Preparation** | Conversion en masse CATPart -> CATComposer `.smg` | `conversion` |
| **3. Traitement** | Couleur des SIN mono-couleur dans le SMGXML + optimisation arbo | `smgxml` (recolor, nouveau), `colorization`, `tree`, `optimize` |
| **4. Integration** | Remplacer l'ancienne piece par la nouvelle dans le SMGXML | `smgxml` (rename, nouveau), `replacement` |
| **5. Controle Qualite** | Checklist de verification des pieces dans l'assemblage | `qc` (nouveau, checklist interactive) |

- **Identification** lit le `.xlsm` (openpyxl, valeurs seules) : detection
  tolerante des colonnes (CATPart, designation, SIN, version, "a traiter",
  couleur). Liste aussi le contenu d'un `.zip` DE en metadonnees seules.
- **SMGXML** lit/edite le fichier texte CATComposer : `recolor` (etape 3) et
  `rename` (etape 4). **Dry-run par defaut** ; en mode `apply`, ecrit le fichier
  en conservant une copie `.bak`. Les noms d'attributs exacts (`NAME_ATTRS`,
  `COLOR_ATTR`, format couleur) sont parametres dans `core/smgxml.py` avec des
  `TODO` a confirmer sur un SMGXML reel.
- La **Source** accepte un dossier OneDrive synchronise, un **partage reseau UNC**
  (`\\serveur\...`) ou un dossier local — il suffit de configurer la racine.

Conforme a [`STANDARD_POC.md`](../../STANDARD_POC.md). Bootstrap depuis
[`apps/_template`](../_template/).

## Auth

**Palier** : 1 - local seul, bind `127.0.0.1`, pas d'authentification.

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| LLM | Mistral via `httpx` async + SSE (pas de SDK) |
| Frontend | React 18 + TS + Vite + Tailwind + RHF + Zod + i18next + Zustand + TanStack Query |
| UI | Skin CSS `frontend/src/styles/preview-skin.css` (écart #3/#4 assumé, voir ci-dessous) + primitives `@internal/ui` (`FileDropzone`) |
| Persistance | SQLite (`backend/data/catia-toolbox.db`), Alembic des J1 |

## Workflow (module Arborescence ; les autres modules suivent le meme schema import -> analyse -> plan)

1. **Import** : scanner un dossier local (`POST /imports/scan`, metadonnees
   seules) ou importer un listing CSV / JSON (`POST /imports/upload`).
2. **Arborescence** : metriques (profondeur, fan-out, doublons de noms,
   nesting profond, coherence de nommage) + arbre imbrique.
3. **Suggestions** : `POST /imports/{id}/optimize` (SSE) genere un plan
   `{old_path, new_path, action, rationale}`. Sans cle Mistral, le baseline
   deterministe (regroupement par type, normalisation des noms) suffit.
4. **Export** : `GET /runs/{id}/export.csv` et `GET /runs/{id}/export.script?os=bat|sh`.

## Endpoints

| Methode | Route | Role |
|---|---|---|
| GET | `/api/v1/health` | Liveness + statut LLM |
| GET/POST | `/api/v1/settings` (+ `/test`) | Config Mistral runtime |
| GET | `/api/v1/admin/stats` | Compteurs (imports/nodes/runs/suggestions) |
| POST | `/api/v1/admin/reset/all` (+ `/imports`, `/runs`) | Reset (preserve `app_config`) |
| GET | `/api/v1/browse/roots` | Racines OneDrive configurees (input/output) + auto-detectees |
| POST | `/api/v1/browse/list` | Lister un niveau d'un dossier OneDrive (lazy, confine sous la racine) |
| POST | `/api/v1/imports/scan` \| `/imports/upload` \| `/imports/select` | Creer un import (dossier \| listing \| selection fichiers+dossiers) |
| POST | `/api/v1/runs/{id}/export/save` | Ecrire le plan/script dans le dossier de sortie |
| POST | `/api/v1/identification/nomenclature` \| `/zip` | Etape 1 : parser la nomenclature `.xlsm` \| lister un `.zip` DE |
| GET | `/api/v1/identification` \| `/{id}` \| `/{id}/items` \| `/{id}/export.csv` | Runs / lignes (filtre `to_treat`) / export CATPart |
| POST | `/api/v1/smgxml/inspect` \| `/recolor` \| `/rename` | Etapes 3 & 4 : inspecter / recolorer / renommer le SMGXML (dry-run par defaut, `apply` -> `.bak`) |
| GET | `/api/v1/smgxml` \| `/{id}` \| `/{id}/changes` | Runs SMGXML / changements |
| POST/GET | `/api/v1/qc/checklists` (+ `/{id}`, `/export.csv`) | Etape 5 : checklist QC (creation, consultation, export) |
| PATCH | `/api/v1/qc/items/{id}` | Mettre a jour un item (statut ok/ko/na + commentaire) |
| GET/DELETE | `/api/v1/imports` \| `/imports/{id}` | Lister / consulter / supprimer |
| GET | `/api/v1/imports/{id}/tree` | Arbre imbrique + metriques |
| POST | `/api/v1/imports/{id}/optimize` | Generer le plan (SSE) |
| GET | `/api/v1/imports/{id}/optimize/runs` | Lister les runs |
| GET | `/api/v1/runs/{id}/suggestions` | Lister les suggestions (filtres) |
| PATCH | `/api/v1/suggestions/{id}` | Accepter / rejeter |
| POST | `/api/v1/suggestions/bulk-status` | Accepter / rejeter en lot |
| GET | `/api/v1/runs/{id}/export.csv` \| `/export.script` | Plan CSV / script dry-run |
| POST | `/api/v1/diff` | Comparer deux imports (pieces modifiees) |
| GET | `/api/v1/diff/{id}/entries` \| `/export.csv` | Entrees du diff / export |
| POST | `/api/v1/imports/{id}/check` | Lancer les verifications |
| GET | `/api/v1/checks/{id}/results` \| `/export.csv` | Resultats / export |
| POST | `/api/v1/imports/{id}/conversion` | Plan de conversion Composer |
| GET | `/api/v1/conversions/{id}/items` \| `/export.csv` \| `/export.script` | Items / CSV / script Composer (win32com .py) |
| POST | `/api/v1/imports/{id}/replacement` | Plan de remplacement (upload mapping) |
| GET | `/api/v1/replacements/{id}/items` \| `/export.csv` \| `/export.macro` | Items / CSV / macro CATIA |
| POST | `/api/v1/imports/{id}/colorization` | Plan de colorisation (by_change / by_type / by_depth) |
| GET | `/api/v1/colorizations/{id}/items` \| `/export.csv` \| `/export.macro` | Items / CSV / macro CATIA V5 |
| GET | `/api/v1/colorizations/{id}/export.composer.py` | Script Composer (win32com .py, DRY_RUN) |
| GET | `/api/v1/colorizations/{id}/simulation.svg` | Simulation visuelle (SVG : 1 tuile coloree / piece) |

## Demarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Le backend
ecoute sur http://127.0.0.1:8005/ (Swagger : `/api/v1/docs`). Sans
`frontend/dist/`, le **preview HTML autonome** (sans Node) est servi a `/`.

Frontend React en mode dev (port 5173), depuis la racine du monorepo :

```bash
pnpm install
pnpm dev:catia-toolbox
```

## Ecarts au standard

> Format STANDARD_POC.md §12. Date : 2026-06-01.

1. **Scan de dossier local** (`POST /imports/scan` → `os.walk` hors
   `backend/data/storage/`). *Regle touchee* : §3 (I/O hors stockage applicatif).
   *Justification* : coeur fonctionnel — lire l'arborescence exportee sur disque.
   *Mitigations* : lecture des **metadonnees uniquement** (nom, taille, mtime,
   chemin relatif, extension) — jamais le contenu ; liens symboliques ignores ;
   cap `max_nodes` (defaut 20000) ; aucune ecriture. *Retour au standard* :
   permanent (dans le perimetre du POC).

2. **Action non destructive forcee** (note de design, pas un ecart). Le backend
   ne deplace / renomme / supprime jamais : il produit un plan (CSV) + un script
   (`.bat` / `.sh`) que l'utilisateur relit et execute lui-meme. Aucune commande
   `del` / `rm` n'est generee.

3. **Connexion OneDrive = dossier synchronise local** (`/browse/*`, `/imports/select`).
   *Regle touchee* : §8 (perimetre local-first) — **respectee** : OneDrive est lu
   via son dossier synchronise sur disque, **sans** connexion cloud / OAuth /
   Microsoft Graph. *Mitigations* : navigation et import en **metadonnees seules**,
   confines sous la racine configuree (anti path-traversal `safe_under_root`),
   liens symboliques ignores, cap `max_nodes`. *Retour au standard* : permanent
   (dans le perimetre du POC).

4. **Ecriture des livrables dans le dossier OneDrive de sortie**
   (`POST /runs/{id}/export/save`). *Regle touchee* : §3 / §7 (I/O hors stockage
   applicatif `data/storage/`). *Justification* : livrer le plan / script
   directement dans le dossier OneDrive choisi par l'utilisateur. *Mitigations* :
   **seul point d'ecriture** du backend ; ecrit uniquement des **livrables
   generes** (CSV / scripts dry-run), **jamais** une piece CATIA ; confine sous la
   racine output (`safe_under_root`) ; nom de fichier assaini (`safe_filename`) ;
   aucune commande `del` / `rm`. *Retour au standard* : permanent (dans le
   perimetre du POC). La racine output doit etre configuree dans Parametres.

5. **Edition en place du SMGXML** (`POST /smgxml/recolor|rename` avec
   `apply=true`). *Regle touchee* : posture plan-only / I/O hors `data/storage/`.
   *Justification* : les etapes 3 et 4 du process demandent de modifier le
   SMGXML (couleur, renommage de pieces) directement dans l'ecosysteme moteur.
   *Mitigations* : **dry-run par defaut** (rien ecrit sans `apply` explicite) ;
   copie **`.bak`** systematique avant ecriture ; fichier confine sous la racine
   configuree ; **uniquement** le SMGXML est modifie (jamais une piece CATIA) ;
   confirmation double-clic cote UI. *Retour au standard* : permanent (coeur
   fonctionnel du POC).

6. **Lecture du contenu de fichiers utilisateur** (nomenclature `.xlsm`,
   `.zip` DE, SMGXML). *Regle touchee* : §3 (lecture de contenu, pas seulement
   metadonnees). *Justification* : coeur fonctionnel des etapes 1/3/4.
   *Mitigations* : lecture **seule** ; openpyxl en `read_only` valeurs seules ;
   `.zip` liste sans extraction ; aucune donnee persistee hors la DB applicative.

7. **Skin CSS au lieu de `@internal/ui`** (regles #3 / #4). *Justification* :
   pour un rendu visuellement coherent avec les POCs recents (corpus-agent /
   doc-writer), le React reutilise un CSS sur-mesure
   `frontend/src/styles/preview-skin.css` (classes `.card/.btn/.kpi/.badge/`
   `.nav-item/.tree/.pill/...`) plutot que les composants `@internal/ui`. Les
   variables CSS reprennent les valeurs de `design-tokens/tokens.json` (`:root`
   clair, `.dark` sombre) — pas de hex « magique ». Les primitives riches
   (`FileDropzone`) viennent quand meme de `@internal/ui`. *Retour au standard* :
   migrer les classes skin vers `@internal/ui` si l'app est perennisee.
