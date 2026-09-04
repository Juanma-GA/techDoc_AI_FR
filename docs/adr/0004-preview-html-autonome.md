# ADR 0004 — Preview HTML autonome servie par FastAPI quand `frontend/dist/` est absent

- **Status** — Superseded (2026-08-24)
- **Scope** — Tous les POC du monorepo. Concerne le mode de rendu UI par défaut quand Node n'est pas disponible côté utilisateur.
- **Reference historique** — [`STANDARD_POC.md`](../../STANDARD_POC.md) §10 et §9. Cette décision est remplacée par le standard React/Vite obligatoire.

> Cette ADR documente une décision historique. Elle ne définit plus le comportement conforme du monorepo.

---

## Contexte

Les POC du monorepo ciblent un **palier 1 local-first strict** : double-clic sur `apps/<poc>/start.bat`, le backend démarre et le navigateur s'ouvre. La contrainte forte côté utilisateur est qu'**il n'est pas garanti d'avoir Node 20 + pnpm installés**. Beaucoup d'utilisateurs cibles (collègues métier, démonstrations chez le client, postes verrouillés sans droits admin) n'ont que Python.

Trois options ont été considérées :

1. **Imposer Node en prérequis** — alignement avec le mode dev React/Vite mais brise la promesse « seul Python 3.11+ est requis » de [STANDARD_POC.md §9](../../STANDARD_POC.md#9-lanceurs-locaux-et-packaging).
2. **Toujours pre-builder `frontend/dist/` et committer** — supprime la dépendance Node côté utilisateur mais alourdit le repo (≈ 1-3 MB par POC, conflits de merge sur les bundles minifiés) et casse la cohérence (`dist/` étant un artefact de build, pas un source).
3. **Servir une UI fallback en HTML/CSS/JS vanilla depuis FastAPI** quand `frontend/dist/` est absent — c'est ce qu'on retient.

## Décision

Tout POC fournit **deux modes de rendu UI**, sélectionnés à l'exécution par `_mount_frontend()` dans `backend/app/main.py` :

- **Si `apps/<poc>/frontend/dist/` existe** → mount Vite SPA (`_mount_vite_dist`). Mode pour le dev qui a buildé ou pour les packages partageables produits avec Node disponible.
- **Sinon** → render `preview.html` à `/` (`_mount_preview`). Mode par défaut quand le user n'a que Python 3.11+.

Les routes `/api/v1/*` sont enregistrées **avant** le catch-all UI pour garder la priorité.

### Composants

| Fichier | Rôle |
|---|---|
| `backend/app/templates/preview.html` | UI vanilla JS complète : sidebar + topbar + onglets Home / Architecture / Données / Paramètres + onglets métier. ASCII pur dans les strings inline ; les accents passent par l'i18n FR injecté dynamiquement. |
| `backend/app/api/preview.py` | Renderer Python qui lit `design-tokens/tokens.json` + `frontend/src/locales/fr.json`, remplace les placeholders `/*__CSS_VARS__*/` et `/*__I18N_FR__*/` du template, retourne `HTMLResponse`. |
| `backend/app/main.py` | `_mount_frontend()` sélectionne le bon mode. Les deux modes consomment **la même** API REST. |

### Contraintes imposées au preview HTML

- **Tokens design uniques** — toutes les couleurs viennent de `tokens.json` via `_build_css_vars()`, aucun hex en dur dans `preview.html`. Le toggle dark/light est piloté par la classe `.dark` sur `<html>`, comme côté React.
- **i18n auto-switch FR ↔ EN** — fonction `t(key)` + attribut `data-i18n="key"`. Dictionnaire inline dans le `<script>` (injecté par `preview.py`). Persistance `localStorage["<poc>-lang"]`.
- **Theme toggle dark/light** — bouton SVG Sun/Moon dans la sidebar-header, snippet anti-flash dans `<head>` avant tout `<link>`, persistance `localStorage["theme"]`.
- **Confirmation actions destructrices** — pattern double-clic (1er clic arme avec label « Cliquer encore pour confirmer », 2e clic dans les 3 s exécute). Pas de `alert()` / `confirm()` natifs (cf. règle 2 de [`CLAUDE.md`](../../CLAUDE.md)).
- **Classes CSS standardisées** — `.btn[.primary|.secondary|.ghost|.danger|.small]`, `.card`, `.kpi-grid`, `.arch-flow`, `.banner[.warn]`, `.badge[.ok|.warn|.danger|.info]` (cf. [STANDARD_POC.md §10](../../STANDARD_POC.md#10-preview-html-autonome-sans-node)).

## Conséquences

### Positives

- **« Seul Python 3.11+ est requis »** redevient une promesse tenable. Un collègue qui reçoit un POC packagé (`.zip` produit par `package.bat`) lance `start.bat` sans avoir à installer Node.
- **Cohérence visuelle entre les deux modes** — les CSS variables émises depuis `tokens.json` sont identiques en mode Vite et en mode preview. Le toggle dark/light marche au pixel près des deux côtés.
- **API REST partagée** — le preview consomme exactement les mêmes endpoints que le React. Toute régression API impacte les deux modes de la même façon, ce qui économise les tests end-to-end.
- **Démos rapides** — pour valider un parcours métier sur un POC en cours d'écriture, plus besoin d'attendre `pnpm install && pnpm build`. Le backend démarre et le preview est dispo immédiatement.

### Négatives / Coûts

- **Deux UI à maintenir** — chaque feature qui mérite d'apparaître dans le preview doit être implémentée deux fois (une en React/`@internal/ui`, une en vanilla JS dans `preview.html`). En pratique, le preview ne reprend que les parcours **standards** (Home, Architecture, Données, Paramètres + 1 ou 2 onglets métier essentiels), pas l'intégralité du React.
- **Pas de bundler dans le preview** — le fichier `preview.html` peut grossir (480 lignes pour `pdf-reviewer`, 1543 pour `ftm-v2`). Documenté comme un écart toléré au seuil 200 lignes de [`CLAUDE.md`](../../CLAUDE.md) car le split nécessiterait un bundler. Atténuation : factoriser le maximum côté tokens + render functions JS bien nommées.
- **Pas de hot reload côté preview** — modifier `preview.html` impose un restart d'uvicorn (ou Ctrl+R navigateur si le contenu rendu n'a pas changé). Acceptable en pratique vu la fréquence d'édition.

## Alternatives étudiées et rejetées

- **Bundler le React build dans le ZIP** (option 2) — augmente le poids des ZIPs partagés, force le packager à avoir Node, et committer le `dist/` créerait des conflits de merge sur les bundles minifiés. Le packaging avec `--embed-python` (cf. `scripts/package_TEMPLATE.py`) règle déjà la portabilité Python sans toucher au front.
- **Servir un index Swagger ou Redoc à `/`** comme UI fallback — testé, jugé insuffisant. Les utilisateurs métier ne savent pas manipuler Swagger ; il leur faut une UI orientée parcours (dropzones, KPI, formulaires de config).
- **Streamlit comme UI fallback** — banni par [STANDARD_POC.md §3.1](../../STANDARD_POC.md#31-stack) (re-run du script à chaque interaction, pas de séparation back/front).

## Suivi

- L'extension `@internal/ui` reste la source unique des primitives **côté React**. Le preview en réimplémente certaines (`btn`, `card`, `kpi`) **uniquement parce qu'il n'a pas accès à `@internal/ui`** ; ces réimplémentations doivent rester visuellement identiques.
- Si un POC dépasse 4-5 onglets métier dans le preview, c'est généralement le signal qu'il est temps de builder le frontend Vite (au moins une fois) plutôt que d'étendre `preview.html`.
