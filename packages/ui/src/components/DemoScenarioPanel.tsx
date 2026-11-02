import { useState } from "react";

import { Button } from "./Button";
import { Card, CardContent, CardHeader, CardTitle } from "./Card";
import { Input } from "./Input";
import { Select } from "./Select";
import { Textarea } from "./Textarea";
import { useDemoMode } from "./DemoMode";
import type { DemoScenario, DemoScenarioResult } from "../lib/demo";

export type DemoScenarioPanelLabels = {
  title: string;
  description: string;
  scenario: string;
  sampleFiles: string;
  run: string;
  reset: string;
  result: string;
  empty: string;
  error: string;
};

export type DemoScenarioPanelProps = {
  scenarios: readonly DemoScenario[];
  labels: DemoScenarioPanelLabels;
};

function initialInputs(scenario: DemoScenario | undefined): Record<string, string> {
  return Object.fromEntries((scenario?.inputs ?? []).map((field) => [field.id, field.initialValue]));
}

function formatResult(result: DemoScenarioResult): string {
  if (typeof result === "string") return result;
  return JSON.stringify(result, null, 2) ?? "";
}

export function DemoScenarioPanel({ scenarios, labels }: DemoScenarioPanelProps) {
  const { mode, isReady } = useDemoMode();
  const [scenarioId, setScenarioId] = useState(scenarios[0]?.id ?? "");
  const [inputs, setInputs] = useState<Record<string, string>>(() => initialInputs(scenarios[0]));
  const [result, setResult] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);
  const scenario = scenarios.find((item) => item.id === scenarioId) ?? scenarios[0];

  if (!isReady || mode !== "demo") return null;

  if (!scenario) {
    return (
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>{labels.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-fg-dim">{labels.empty}</p>
        </CardContent>
      </Card>
    );
  }

  const activeScenario = scenario;

  function changeScenario(nextId: string) {
    const nextScenario = scenarios.find((item) => item.id === nextId);
    if (!nextScenario) return;
    setScenarioId(nextId);
    setInputs(initialInputs(nextScenario));
    setResult(null);
    setHasError(false);
  }

  function resetScenario() {
    setInputs(initialInputs(activeScenario));
    setResult(null);
    setHasError(false);
  }

  function runScenario() {
    try {
      setResult(
        formatResult(activeScenario.run({ inputs, files: activeScenario.files ?? [] })),
      );
      setHasError(false);
    } catch {
      setResult(null);
      setHasError(true);
    }
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{labels.title}</CardTitle>
        <p className="text-sm text-fg-dim">{labels.description}</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="label">{labels.scenario}</span>
          <Select
            value={activeScenario.id}
            options={scenarios.map((item) => ({ value: item.id, label: item.title }))}
            onChange={(event) => changeScenario(event.target.value)}
          />
        </label>

        <div>
          <h3 className="font-medium">{activeScenario.title}</h3>
          <p className="text-sm text-fg-dim">{activeScenario.description}</p>
        </div>

        {activeScenario.inputs.map((field) => (
          <label key={field.id} className="flex flex-col gap-1">
            <span className="label">{field.label}</span>
            {field.multiline ? (
              <Textarea
                value={inputs[field.id] ?? ""}
                onChange={(event) =>
                  setInputs((current) => ({ ...current, [field.id]: event.target.value }))
                }
              />
            ) : (
              <Input
                value={inputs[field.id] ?? ""}
                onChange={(event) =>
                  setInputs((current) => ({ ...current, [field.id]: event.target.value }))
                }
              />
            )}
          </label>
        ))}

        {activeScenario.files?.length ? (
          <section>
            <h3 className="label">{labels.sampleFiles}</h3>
            <ul className="text-sm text-fg-dim">
              {activeScenario.files.map((file) => (
                <li key={file.id}>{file.name}</li>
              ))}
            </ul>
          </section>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button onClick={runScenario}>{labels.run}</Button>
          <Button variant="secondary" onClick={resetScenario}>
            {labels.reset}
          </Button>
        </div>

        {hasError ? <p role="alert" className="text-danger">{labels.error}</p> : null}
        {result !== null ? (
          <div>
            <span className="label">{labels.result}</span>
            <pre
              aria-label={labels.result}
              className="max-h-60 overflow-auto whitespace-pre-wrap break-words rounded-sm border border-md bg-surface-sunken p-3 text-sm"
            >
              {result}
            </pre>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}