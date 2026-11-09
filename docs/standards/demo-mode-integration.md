# Demo Mode And Shared Identity Integration

TECHDOC_AI adaptation of the [framework guide](../../framework/docs/standards/demo-mode-integration.md).
The framework document owns the reusable contract; this file covers consumer
integration and branding.

This guide describes the reusable frontend contract and the template backend setting. It is supporting guidance, not a new application profile.

## Shared Contract

`@internal/ui` exports `DemoModeProvider`, `useDemoMode`, `DemoModeSelector`, `DemoModeSettingsCard`, `DemoModeBadge`, and `DemoScenarioPanel`. Scenario types and the in-memory file helper are exported as `DemoScenario`, `DemoInputField`, `DemoSampleFile`, `DemoScenarioContext`, `DemoScenarioResult`, and `createDemoFile`.

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

Use `DemoModeSettingsCard` in Settings (it wraps `DemoModeSelector` with the title, hint and save-error message; the app keeps the mutation that persists `demo_enabled`, see `framework/apps/_template/frontend/src/routes/DemoModeSettings.tsx`) and update the app's Settings API. Use `useDemoMode` in routes, `DemoModeBadge` in the application shell, and mount `DemoScenarioPanel` only for a ready demo mode. The settings card, selector, badge, input editing, run action, result display, and scenario reset are shared; an application registers only its own scenario definitions and local runner.

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

The framework template adds optional `demo_enabled` to `/api/v1/settings` and stores it as the `AppConfig` key `demo_enabled`. Missing means `false` (normal mode). Follow that small pattern in an app's own backend Settings API; do not store the mode or scenario data in browser storage. Existing `AppConfig` reset-preservation behavior keeps the preference intact.

The framework template's Home route registers one neutral text-summary scenario and one synthetic `.txt` sample defined in locale resources. It has no business workflow and its runner performs only local word/character counts.

## Consumer-Owned Brand

Company branding is not part of the framework's `@internal/ui`. TECHDOC_AI keeps its mark and favicon integration in [`packages/techdoc-brand/`](../../packages/techdoc-brand/), while the framework `AppShell` remains generic:

```tsx
import { AppShell, setAi4TechDocFavicon } from "@internal/techdoc-brand";

<AppShell ... />
setAi4TechDocFavicon();
```

The asset is [`packages/techdoc-brand/src/assets/ai4techdoc.svg`](../../packages/techdoc-brand/src/assets/ai4techdoc.svg). Keep it in this consumer-owned package; do not add a company logo to the framework submodule.