import { Button, Checkbox, Select, Textarea, createDemoFile, useDemoMode, type DemoSampleFile } from "@internal/ui";
import { FlaskConical, Upload } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ENGINE_START_FILES, HYDRAULIC_FILES, sampleSize } from "../../demo/samples";

type Scenario = { id: string; files: readonly DemoSampleFile[] };

// Mode demo integre a l'assistant : on choisit des fichiers et un prompt factices, qui sont joints
// et pre-remplis comme une saisie normale. Ecart documente (README) au flux local du standard demo.
const DEFAULT_SCENARIO: Scenario = { id: "hydraulic", files: HYDRAULIC_FILES };
const SCENARIOS: readonly Scenario[] = [DEFAULT_SCENARIO, { id: "engineStart", files: ENGINE_START_FILES }];

type Props = { disabled: boolean; onLoad: (files: File[], prompt: string) => void };

export function useDemoActive() {
  const { mode, isReady } = useDemoMode();
  return isReady && mode === "demo";
}

export function DemoButton({ open, disabled, onToggle }: { open: boolean; disabled: boolean; onToggle: () => void }) {
  const { t } = useTranslation();
  return (
    <Button variant={open ? "secondary" : "ghost"} size="sm" disabled={disabled} aria-expanded={open} onClick={onToggle}>
      <FlaskConical size={14} aria-hidden /> {t("demo.button")}
    </Button>
  );
}

export function DemoPicker({ disabled, onLoad }: Props) {
  const { t } = useTranslation();
  const [scenarioId, setScenarioId] = useState(DEFAULT_SCENARIO.id);
  const [checked, setChecked] = useState<Set<string>>(() => new Set(DEFAULT_SCENARIO.files.map((f) => f.id)));
  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? DEFAULT_SCENARIO;
  const [prompt, setPrompt] = useState(() => t(`demo.${DEFAULT_SCENARIO.id}.prompt`));

  const selectScenario = (id: string) => {
    const next = SCENARIOS.find((s) => s.id === id) ?? DEFAULT_SCENARIO;
    setScenarioId(next.id);
    setChecked(new Set(next.files.map((f) => f.id)));
    setPrompt(t(`demo.${next.id}.prompt`));
  };

  const toggle = (id: string) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selected = scenario.files.filter((f) => checked.has(f.id));

  return (
    <div className="flex max-h-[55%] min-h-0 shrink-0 flex-col gap-3 overflow-y-auto rounded border border-dashed bg-card p-3" data-testid="demo-picker">
      <p className="text-fg">{t("demo.pickerTitle")}</p>
      <p className="text-fg-dim">{t("demo.pickerHint")}</p>
      <label className="flex flex-col gap-1">
        <span className="text-fg-dim">{t("demo.scenarioLabel")}</span>
        <Select
          size="sm"
          value={scenarioId}
          onChange={(e) => selectScenario(e.target.value)}
          options={SCENARIOS.map((s) => ({ value: s.id, label: t(`demo.${s.id}.title`) }))}
        />
      </label>
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-fg-dim">{t("demo.sampleFiles")}</legend>
        {scenario.files.map((f) => (
          <div key={f.id} className="flex min-w-0 items-center gap-2">
            <Checkbox id={`demo-${f.id}`} checked={checked.has(f.id)} onCheckedChange={() => toggle(f.id)} />
            <label htmlFor={`demo-${f.id}`} className="min-w-0 flex-1 truncate" title={f.name}>
              {f.name}
            </label>
            <span className="shrink-0 whitespace-nowrap text-fg-dim">{Math.round(sampleSize(f) / 1024)} Ko</span>
          </div>
        ))}
      </fieldset>
      <label className="flex flex-col gap-1">
        <span className="text-fg-dim">{t("demo.promptLabel")}</span>
        <Textarea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      </label>
      <div className="flex justify-end">
        <Button
          size="sm"
          disabled={disabled || (selected.length === 0 && !prompt.trim())}
          onClick={() => onLoad(selected.map(createDemoFile), prompt.trim())}
        >
          <Upload size={14} aria-hidden /> {t("demo.use")}
        </Button>
      </div>
    </div>
  );
}
