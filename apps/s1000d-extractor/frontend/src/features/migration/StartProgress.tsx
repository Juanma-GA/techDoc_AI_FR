import type { StartProgressState } from "./useMigrationWizard";

export function StartProgress({ progress }: { progress: StartProgressState | null }) {
  if (!progress) return null;
  const pct = Math.max(0, Math.min(100, progress.pct));
  return <div className="grow space-y-2" role="status">
    <div className="flex justify-between gap-3 text-sm text-fg-dim">
      <span>{progress.label}</span><span>{pct}%</span>
    </div>
    <progress className="w-full accent-brand" value={pct} max={100} aria-label={progress.label} />
  </div>;
}
