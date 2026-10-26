# Demo Mode And Shared Identity Integration

This guide describes the reusable frontend contract and the template backend setting. It is supporting guidance, not a new application profile.

## Shared Contract

`@internal/ui` exports `DemoModeProvider`, `useDemoMode`, `DemoModeSelector`, `DemoModeBadge`, and `DemoScenarioPanel`. Scenario types and the in-memory file helper are exported as `DemoScenario`, `DemoInputField`, `DemoSampleFile`, `DemoScenarioContext`, `DemoScenarioResult`, and `createDemoFile`.

The application reads its persisted `demo_enabled` setting and supplies the mode once near the app root:

```tsx
const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

<DemoModeProvider
  mode={demoEnabled ? "demo" : "normal"}
  isReady={settingsQuery.isSuccess}
>
  <App />
</DemoModeProvider>
```

Use `DemoModeSelector` in Settings and update the app's Settings API. Use `useDemoMode` in routes, `DemoModeBadge` in the application shell, and mount `DemoScenarioPanel` only for a ready demo mode. The selector, badge, input editing, run action, result display, and scenario reset are shared; an application registers only its own scenario definitions and local runner.

## Register Scenarios

Scenarios are TypeScript data in the owning app. Inputs carry their own initial values; optional sample files carry inline or generated content. `run` is synchronous and receives only the current inputs and the registered files:

```tsx
const scenarios: DemoScenario[] = [
  {
    id: "text-summary",
    title: t("demo.textSummary.title"),
    description: t("demo.textSummary.description"),
    inputs: [{ id: "text", label: t("demo.textSummary.input"), initialValue: "Synthetic text" }],
    files: [{ id: "sample", name: "sample.txt", mediaType: "text/plain", content: "Synthetic sample." }],
    run: ({ inputs, files }) => `${inputs.text} (${files.length} sample file)`,
  },
];
```

Pass the list and translated panel labels to `DemoScenarioPanel`. It keeps edits and results in component memory only; Reset restores the selected scenario's initial inputs and clears its result. `createDemoFile(sample)` creates a browser `File` from the registered content without fetching anything.

Runners must be deterministic and local: no `fetch`, API client, LLM, or external service, and no forwarding demo inputs/files into the normal application request path. Keep normal business data and demo scenario state in separate code paths. Do not persist demo inputs, outputs, or files. The mode preference itself is not demo data.

Register only synthetic, app-specific examples. Keep file content inline or generate it in memory where practical. If an app needs tracked fixtures, follow the app's documented repository content policy; do not add client documents or binaries prohibited by that policy. This shared package intentionally supplies no business sample dataset.

## Persist The Mode

The template adds optional `demo_enabled` to `/api/v1/settings` and stores it as the `AppConfig` key `demo_enabled`. Missing means `false` (normal mode). Follow that small pattern in an app's own backend Settings API; do not store the mode or scenario data in browser storage. Existing `AppConfig` reset-preservation behavior keeps the preference intact.

The template's Home route registers one neutral text-summary scenario and one synthetic `.txt` sample defined in locale resources. It has no business workflow and its runner performs only local word/character counts.

## Use The Shared Icon

The canonical asset is [`packages/ui/src/assets/ai4techdoc.svg`](../../packages/ui/src/assets/ai4techdoc.svg), exposed by `Ai4TechDocLogo` from `@internal/ui`:

```tsx
import { Ai4TechDocLogo } from "@internal/ui";

<AppShell headerStart={<Ai4TechDocLogo alt="" />} ... />
```

The source is already SVG; no raster conversion is needed. It selects its light/dark palette from the system `prefers-color-scheme` setting (rather than the app's theme toggle). Use the shared component rather than copying the asset into an application. Call `setAi4TechDocFavicon()` once from the frontend entry point (for example, `src/main.tsx`) to register the same SVG as the browser tab icon. It creates or updates the `<link rel="icon" type="image/svg+xml">` element using Vite's bundled asset URL.