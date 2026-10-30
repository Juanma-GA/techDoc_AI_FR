# ADR 0005 — Design system v2 : tokens générés, canaux RGB, palette claire, polices partagées

- **Status** — Accepted (2026-10-30)
- **Scope** — `design-tokens/`, `packages/ui/`, `apps/_template/` et toutes les apps frontend du monorepo.
- **Reference** — [`STANDARD_POC.md`](../../STANDARD_POC.md) §5, [supplément design system](../standards/design-system.md).

---

## Contexte

Audit du framework UI (octobre 2026) :

- `theme.css` était maintenu à la main en parallèle de `tokens.json`, avec des commentaires contradictoires (`.light` vs `:root` clair).
- Le preset Tailwind exposait les couleurs en `var(--color-x)` contenant un hex : avec Tailwind 3.4, les modificateurs d'opacité (`bg-success/15`, `border-danger/40`, `bg-bg/70`) ne généraient **aucun CSS**. Badges, toasts, overlays et plusieurs composants d'apps étaient donc rendus sans fond.
- Aucun token « texte sur fond de marque » : les boutons primaires et l'onglet actif utilisaient `text-fg`, quasi noir en mode clair.
- Ombres, rayons et polices écrits en dur dans le CSS partagé ; une seule ombre (sombre) pour les deux thèmes.

## Décision

1. `tokens.json` est l'unique source ; `theme.css` est **généré** par `design-tokens/scripts/build-theme.mjs` et vérifié par `pnpm tokens:check` (test + `check_standard.sh`).
2. Chaque token hex émet `--color-<nom>` (couleur complète, compatible) **et** `--color-<nom>-rgb` (canaux). Le preset consomme `rgb(var(--color-<nom>-rgb) / <alpha-value>)`, ce qui réactive les opacités Tailwind.
3. Nouveaux tokens sémantiques : `brand.fg`, `brand.hover`, `brand.text`, `brand.soft`, `surface.sunken`, `focus.ring`, `nav.active-bg/fg`, `overlay`, ombres thémées (`shadow.card`, `shadow.popover`), échelles `radius`, `fontSize`, `motion`, et polices exposées en variables CSS avec des polices système de repli.

## Conséquences

### Positives

- Les opacités fonctionnent dans tous les composants partagés et les apps sans modification du markup.
- Plus de dérive entre `tokens.json` et `theme.css`.
- Les apps qui lisent `var(--color-*)` en CSS ne cassent pas : les noms et le format historiques sont conservés.

### Négatives / Coûts

- Un token ajouté doit être régénéré (`pnpm tokens:build`) ; oublier la régénération fait échouer `check_standard.sh`.
- Les tokens définis avec une transparence (bordures, `brand.soft`, `overlay`) n'acceptent pas de modificateur d'opacité.

## Alternatives étudiées et rejetées

- **Remplacer les valeurs `--color-*` par des canaux RGB** : casse toutes les feuilles CSS d'apps qui utilisent `var(--color-*)` comme couleur.
- **`color-mix()` dans le preset** : correct, mais support navigateur moins homogène dans les WebView desktop ciblées et sortie plus verbeuse.
- **Migration vers Tailwind 4** : hors périmètre, impacte toutes les apps.
