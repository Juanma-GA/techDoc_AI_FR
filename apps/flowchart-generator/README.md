# Flowchart Generator (logigrammes industriels)

> **Palier 1 - local seul.** Pas d'authentification, bind `127.0.0.1` uniquement. Port par defaut `8010`.

## Purpose

Generer des logigrammes complexes de diagnostic et de depannage industriel (panne vehicule, systeme complexe, procedure de maintenance) a partir de plusieurs entrees, et les exporter dans les formats utilises par l'industrie.

## Maturity

**Status:** POC fonctionnel - backend teste (pytest), frontend type-checke et builde.

## Features

- **Assistant conversationnel** (mode unique de l'Editeur, disposition deux colonnes assistant | logigramme, menu lateral repliable) : on decrit la panne, l'assistant genere un plan de maintenance sous forme de logigramme, puis on itere en langage naturel (ajouter un controle, une consigne de securite...) ; chaque modification met a jour l'apercu en direct.
- **Validation avant export** : les telechargements ne sont proposes qu'apres clic sur « Valider le logigramme » ; toute modification ulterieure annule la validation.
- **Entrees via l'assistant** : description en texte libre (structuree par Mistral, repli deterministe si LLM OFF), script DSL ou JSON colle dans le chat (importe directement sans LLM), ou **fichiers joints** (bouton trombone ou glisser-deposer) :
  - `.xlsx`, `.xlsm`, `.csv` contenant des colonnes d'etapes (au minimum `Libelle`), `.json`, `.dsl`, `.flow` : importes directement comme logigramme (un nouvel import remplace le logigramme courant) ;
  - `.txt`, `.md`, `.docx`, `.pdf` (texte par page), `.pptx` (texte des diapositives et notes), et tout Excel/CSV **sans** colonnes d'etapes (toutes les feuilles sont lues) : documents de reference (10 max, 50 000 caracteres chacun, tronques au-dela ; 120 000 caracteres au total envoyes a Mistral par tour) transmis a l'assistant pour generer ou modifier le logigramme. Plusieurs fichiers de formats differents peuvent etre joints en une fois.
- **Mode demo** (Parametres > Mode de l'application) : badge « Mode demo » et bouton **Demo** dans la zone de saisie de l'assistant (chariot telescopique fictif TELEMAX TH-3500). Le selecteur permet de choisir un scenario, de cocher les fichiers **factices** a joindre et d'editer la demande type ; « Joindre et preremplir » joint les fichiers et preremplit la saisie, puis on suit la marche classique (Envoyer, iterer, Valider, exporter). Deux scenarios : *Diagnostic hydraulique* (procedure Word, donnees de maintenance Excel, consignes HSE PDF, REX PowerPoint, joints comme documents de reference) et *Non-demarrage moteur* (tableau Excel d'etapes importe directement en logigramme). Fichiers sources : `frontend/src/demo/files/`, embarques dans le bundle (aucun telechargement).
- **Types d'etapes industriels** : `start`, `end`, `process`, `decision`, `check` (mesure/controle), `repair`, `safety` (consignation/EPI), `io`, `document`, `subprocess`, `connector`.
- **Details par etape** : reference procedure, valeur attendue, outillage, consigne de securite, duree.
- **Couloirs** (acteurs/roles), titre, systeme, code defaut, orientation `TB`/`LR`.
- **Sorties** :

| Format | Usage |
|---|---|
| Mermaid (`.mmd`) | Markdown, wikis, GitLab/GitHub |
| SVG | Documentation, apercu |
| draw.io (`.drawio`) | diagrams.net ; importable dans **Visio** (pas d'export `.vsdx` natif) |
| BPMN 2.0 (`.bpmn`) | Camunda, Bizagi, Signavio |
| PowerPoint (`.pptx`) | Formes et connecteurs natifs editables |
| Excel (`.xlsx`) | Feuilles Etapes + Transitions, reimportables |
| JSON | Echange, reimport, API |
| S1000D (`.xml`) | Data module fault isolation |

**Limite S1000D** : sortie approchant l'Issue 4.x avec un DMC generique ; non validee contre le schema officiel ni contre une BREX projet.

## Inputs

### DSL

```text
title: Demarrage impossible
system: Circuit de charge
fault_code: P0562
direction: TB
lane Technicien
S [start] Le moteur ne demarre pas
C [check] Mesurer tension batterie {ref: DM-24-00; attendu: 12,4 V; outils: multimetre}
D [decision] Tension OK ?
S -> C -> D
D -> R : non
```

- Noeud : `ID [type] libelle {cle: valeur; ...}` ; cles `ref`, `attendu|expected`, `outils|tools`, `securite|warning`, `duree|duration`.
- Lien : `A -> B -> C`, etiquette optionnelle `: condition`. `#` = commentaire.

### Tableau (xlsx, xlsm, csv - 5 Mo max)

Une ligne par etape. Colonnes reconnues (alias FR/EN) : `id`, `libelle`, `type`, `acteur`, `suivants`, `conditions`, `reference`, `attendu`, `outillage`, `securite`, `duree`. Plusieurs suivants/conditions separes par `;`, `,` ou `|`. Sans colonne `suivants`, les etapes sont chainees dans l'ordre.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `llm`
- `files`
<!-- APP_PROFILES_END -->

## Port

Port cible `8010`. Les launchers basculent sur le premier port libre suivant si occupe. Voir l'[inventaire des applications](../../docs/apps/README.md).

## Prerequisites

- Python 3.11+.
- Node 20 et pnpm 9 pour le build frontend.
- Cle API Mistral uniquement pour l'entree texte structuree par LLM.

## Start

- Windows : double-clic sur `start.bat`.
- Unix : `bash start.sh`.
- Developpement : `pnpm dev:flowchart-generator` depuis la racine.
- Package ZIP : `package.bat` (sortie dans `apps/flowchart-generator/dist/`).

## API (`/api/v1`)

| Methode | Route | Role |
|---|---|---|
| POST | `/parse/text`, `/parse/json`, `/parse/table` | Entree vers graphe |
| POST | `/assistant/chat` | Tour d'assistant : historique (1-100 messages) + graphe courant + documents joints (0-5) -> reponse + graphe modifie |
| POST | `/assistant/attach` | Fichier joint (5 Mo max) -> graphe importe ou document de reference (texte extrait) |
| POST | `/render/preview`, `/render/{fmt}` | Apercu SVG, export |
| GET | `/formats` | Formats disponibles |
| GET/POST | `/flows` ; GET/PUT/DELETE `/flows/{id}` | Logigrammes enregistres |
| GET | `/flows/{id}/export/{fmt}` | Export d'un logigramme enregistre |
| standard | `/health`, `/settings`, `/settings/test`, `/admin/stats`, `/admin/reset/{all,flows}` | Endpoints du standard |

## Persistence

SQLite gitignore `backend/data/flowchart-generator.db`. `AppConfig` conserve la configuration Mistral lors des resets.

## LLM Configuration

Interrupteur `llm_enabled` en Parametres. OFF : `/parse/text` renvoie HTTP 200 avec un decoupage deterministe ligne par ligne (aucun appel Mistral) ; `/assistant/chat` repond HTTP 200 avec ce meme decoupage pour une premiere demande, et sans modification du graphe existant ensuite. Le graphe produit par le LLM est toujours valide et normalise cote serveur.

## Tests

- Backend : `.venv\Scripts\python.exe -m pytest -q` depuis `backend/`.
- Frontend : `pnpm --filter @apps/flowchart-generator-frontend typecheck|lint|build`.
- E2E : `pnpm test:e2e:flowchart-generator` (redirection `/`, fichier DSL joint + validation, menu repliable, assistant).

## Limitations

- Pas d'export Visio `.vsdx` natif (passer par draw.io).
- Mise en page automatique en couches ; pas d'edition graphique a la souris.
- S1000D non valide schema/BREX.
- PDF : texte natif uniquement (pas d'OCR des PDF scannes).

## Standard Deviations

Dependances backend supplementaires : `python-pptx`, `openpyxl` (exports Office, lecture PPTX/Excel joints), `PyMuPDF` (extraction texte des PDF joints).

**Mode demo et traitement serveur** : a la demande produit, le mode demo est integre a l'assistant au lieu du `DemoScenarioPanel` local deterministe du standard demo (`docs/standards/demo-mode-integration.md`). Les fichiers factices selectionnes passent par le vrai endpoint `/assistant/attach` (parsing backend) et la demande preremplie est envoyee par l'utilisateur a `/assistant/chat` (Mistral), afin de demontrer la chaine reelle. `DemoModeProvider`, badge et selecteur de mode restent ceux de `@internal/ui`. Le mode est persiste uniquement dans `AppConfig` (`demo_enabled`), jamais dans le stockage navigateur. Les fichiers de demo sont integres via un plugin Vite local (`?b64`, `vite.config.ts`).

**Onglet Accueil retire** (ecart a CLAUDE.md regle #13, onglets minimum Home / Donnees / Parametres) : supprime a la demande de l'utilisateur, l'Editeur etant le point d'entree unique. `/` et toute route inconnue redirigent vers `/editor`. Onglets presents : Editeur / Donnees / Parametres.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application README template](../../docs/standards/app-readme-template.md)
