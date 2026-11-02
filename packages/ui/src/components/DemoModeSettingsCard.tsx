import { Card, CardContent, CardHeader, CardTitle } from "./Card";
import { type DemoMode, DemoModeSelector } from "./DemoMode";

export type DemoModeSettingsCardLabels = {
  title: string;
  hint: string;
  normal: string;
  demo: string;
  saveError: string;
};

export type DemoModeSettingsCardProps = {
  mode: DemoMode;
  /** Translated texts; the component has no language of its own. */
  labels: DemoModeSettingsCardLabels;
  onModeChange: (mode: DemoMode) => void;
  /** Disable while settings load or a save is pending. */
  disabled?: boolean;
  /** Shows `labels.saveError` when the last save failed. */
  error?: boolean;
  className?: string;
};

/**
 * Settings card "Operating mode" (normal / demo). Presentational: the app owns
 * the query/mutation that persists `demo_enabled`. See
 * docs/standards/demo-mode-integration.md.
 */
export function DemoModeSettingsCard({
  mode,
  labels,
  onModeChange,
  disabled = false,
  error = false,
  className,
}: DemoModeSettingsCardProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{labels.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="m-0 text-sm text-fg-dim">{labels.hint}</p>
        <DemoModeSelector
          mode={mode}
          labels={{ normal: labels.normal, demo: labels.demo }}
          ariaLabel={labels.title}
          disabled={disabled}
          onModeChange={onModeChange}
        />
        {error ? (
          <p role="alert" className="m-0 text-sm text-danger">
            {labels.saveError}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
