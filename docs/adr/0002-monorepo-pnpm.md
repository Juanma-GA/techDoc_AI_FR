# ADR 0002 — Monorepo pnpm + package `@internal/ui`

- **Status** — Partially superseded (2026-11-04); pnpm workspace decisions remain accepted.
- **Scope** — Original in-repo sharing model; shared framework sources now live in the pinned `framework/` submodule.
- **Reference** — [`STANDARD_POC.md`](../../STANDARD_POC.md) §2 (mutualisé
  vs propre au POC) et §5.3 (composants `@internal/ui` canoniques).

---

> This ADR records the original monorepo layout. Its root-level `packages/ui/`
> and `design-tokens/` paths, and its claims of immediate propagation across
> repositories, are historical. Consumers now update the pinned framework
> commit explicitly; see the [framework consumption guide](../../framework/docs/standards/consuming-framework.md).

## Contexte

À court terme nous embarquons FTM Agent v2. À moyen terme, plusieurs
POC IA internes vont vivre côte à côte, chacun ayant besoin de :

- les **mêmes tokens de design** (palette Midnight Executive, fontes,
  layout sidebar 252 px) ;
- les **mêmes composants UI** (Button, Card, Badge, KpiCard,
  ChartCard, Toast, Dialog) — sinon dérive visuelle garantie ;
- la **même configuration TypeScript stricte** ;
- une **même façon de versionner** ces deux artefacts pour qu'une
  régression sur l'un puisse affecter tous les consommateurs.

Sur Legacy POC 5.0 et FTM v1 ces ressources étaient dupliquées par
copier-coller. Coût constaté : un fix CSS dans l'un n'arrivait jamais
dans l'autre.

## Décision

Repo unique organisé en **monorepo pnpm workspace** :

```
.
├── apps/
│   └── <projet>/{backend,frontend}/   # 1 app = 1 produit (ftm-v2, …)
├── packages/
│   └── ui/                            # @internal/ui — composants partagés
├── design-tokens/                     # @internal/design-tokens
├── docs/adr/                          # Architecture Decision Records
├── scripts/                           # check_standard.sh + outils de validation locale
└── legacy/                            # code legacy en lecture seule
```

`pnpm-workspace.yaml` :

```yaml
packages:
  - "apps/*/frontend"
  - "packages/*"
  - "design-tokens"
```

Choix techniques associés :

| Choix | Détail | Pourquoi |
|---|---|---|
| Package manager | **pnpm 9** (corepack) | hardlinks, lockfile unique, monorepo natif |
| Versionning des packages internes | **`workspace:*`** | toujours la version locale, pas de publication intermédiaire |
| Backend Python | **hors workspace pnpm** | Python a son propre packaging (`pyproject.toml`), pnpm ne gagne rien à l'embarquer |
| Tokens | **`@internal/design-tokens`** distribué en sources TS + JSON | consommé par Tailwind preset (TS) et par JS direct (Recharts, SVG inline) |
| Composants | **`@internal/ui` v0.1.0** | atomes (Button/Card/Badge/Toast/Dialog) + métier (KpiCard/ChartCard/EmptyState/LoadingOverlay) |
| TypeScript | `tsconfig.base.json` à la racine, `strict + noUncheckedIndexedAccess + verbatimModuleSyntax` | une seule source de vérité TS |

## Conséquences

### Positives

- **Un seul `pnpm install`** suffit à amorcer tous les fronts.
- **Un fix dans `@internal/ui` se propage immédiatement** à tous les
  apps consommateurs — l'incident inverse (un consommateur casse
  silencieusement faute de mise à jour) devient impossible.
- **Tokens consommés à un seul endroit** : Tailwind preset et code JS
  importent du même `tokens.json`. Le `check_standard.sh` ferraille
  toute couleur hex en dur.
- **Un seul `tsconfig.base.json`** = pas de dérive TS strict entre apps.
- **Cycle dev rapide** : modifier `@internal/ui/Button.tsx` est
  immédiatement visible dans `apps/ftm-v2/frontend` sans rebuild.

### Négatives / Coûts

- **Onboarding plus rigide** : impossible de cloner uniquement le
  frontend FTM. C'est un compromis assumé pour mutualiser.
- **Backend Python en marge** : SQLAlchemy / Alembic / pytest vivent à
  côté du workspace pnpm. La doc `pnpm dev:back` n'utilise pnpm que
  comme proxy de commande (`cd apps/ftm-v2/backend && uvicorn …`).
- **`@internal/ui` non publié sur un registry** : dépendance forte au
  monorepo. Si un projet sort du repo, il faudra publier sur GHCR /
  npm privé (à ré-arbitrer ce moment-là).
- **Lockfile unique** : un upgrade de React touche tout. Convergent
  par construction, mais demande discipline en revue.

## Alternatives étudiées et rejetées

- **Repos séparés par app** — modèle Legacy POC / FTM v1 actuel. Cause
  directe de la duplication observée.
- **Monorepo Turborepo / Nx** — plus de fonctionnalités (cache build
  distribué, graph de dépendances) mais surcoût d'apprentissage non
  justifié au vu de la taille actuelle (1 app + 2 packages).
- **Lerna / Yarn workspaces** — Lerna en maintenance lente ;
  Yarn 1 hors mode, Yarn 4 nécessite migration manuelle. pnpm est
  l'option standard 2026.
- **Publication npm privée de `@internal/ui`** — soulagerait l'export
  hors du repo mais introduit une étape de release entre dev et
  consommation. Reporté tant qu'on reste un seul repo.

## Suivi

Toute nouvelle app interne s'ajoute sous `apps/<nom>/` avec
`backend/` (Python) et/ou `frontend/` (workspace pnpm) et consomme
`@internal/ui` + `@internal/design-tokens`.
