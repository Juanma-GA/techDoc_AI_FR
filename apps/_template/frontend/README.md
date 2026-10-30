# Template Frontend

The demo-mode and shared-identity integration contract is documented in the [Demo Mode And Shared Identity guide](../../../docs/standards/demo-mode-integration.md). This frontend README is copied by `scripts/new_poc.mjs` and remains available after the generated app README is replaced.

## Design System

The visual framework is inherited, not copied. See the [design system supplement](../../../docs/standards/design-system.md).

- `src/index.css` has a single design-system import, `@import "@internal/design-tokens/base.css";`, followed by the three `@tailwind` directives. It provides the theme variables (dark by default, light v2), the self-hosted Inter / JetBrains Mono / Orbitron fonts and the document defaults. Do not add `@fontsource/*` dependencies, font imports, Google Fonts links or a local copy of `theme.css`.
- `index.html` keeps the anti-flash script (dark unless `light` was saved) and `<meta name="color-scheme" content="dark light">`.
- Pages start with `PageHeader` and use `Card`, `FormField`, `Alert`, `Skeleton`, `EmptyState`, `Tabs`, `Table`, `Tooltip` and `CollapsibleSection` from `@internal/ui` (examples: `routes/Home.tsx`, `routes/Data.tsx`, `routes/Settings.tsx`).
- In development (`pnpm dev`), the **Design system** tab (`/design`, `routes/DesignGallery.tsx`) renders every shared component; it is excluded from production builds. Keep it to review both themes, FR/EN and narrow viewports, or delete the route and file if the app does not need it.
- `pnpm test:e2e` runs `tests/e2e/design-system.spec.ts`: dark/light x FR/EN x desktop/760px, checks that the three font faces are really loaded and that `main` has no horizontal overflow, and attaches screenshots to the Playwright report.
