import { ProgressBar } from "@internal/ui";

import type { StartProgressState } from "./useMigrationWizard";

export function StartProgress({ progress }: { progress: StartProgressState | null }) {
  if (!progress) return null;
  return <ProgressBar value={progress.pct} label={progress.label} />;
}
