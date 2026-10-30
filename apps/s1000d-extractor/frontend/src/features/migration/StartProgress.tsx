import type { StartProgressState } from "./useMigrationWizard";

export function StartProgress({ progress }: { progress: StartProgressState | null }) {
  if (!progress) return null;
  const pct = Math.max(0, Math.min(100, progress.pct));
  return <div className="grow space-y-2" role="status">
    <div className="flex justify-between gap-3 text-sm text-fg-dim">
      <span>{progress.label}</span><span>{pct}%</span>
    </div>
    <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={pct} aria-label={progress.label}>
      <span style={{ width: `${pct}%` }} />
    </div>
  </div>;
}
