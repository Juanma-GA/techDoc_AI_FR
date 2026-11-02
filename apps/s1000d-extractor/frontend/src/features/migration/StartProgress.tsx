import type { StartProgressState } from "./useMigrationWizard";

export function StartProgress({ progress }: { progress: StartProgressState | null }) {
  if (!progress) return null;
  const pct = Math.max(0, Math.min(100, progress.pct));
  return <div className="min-w-0 flex-1 space-y-2" role="status">
    <div className="flex justify-between gap-3 text-sm text-fg-dim">
      <span>{progress.label}</span><span>{pct}%</span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-bg-3" role="progressbar" aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={pct} aria-label={progress.label}>
      <div className="h-full bg-brand transition-[width]" style={{ width: `${pct}%` }} />
    </div>
  </div>;
}
