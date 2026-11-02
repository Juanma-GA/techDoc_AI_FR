import { cn } from "../lib/utils";

export type ProgressBarProps = {
  value: number;
  label: string;
  className?: string;
};

function clampProgress(value: number): number {
  if (!Number.isFinite(value)) {
    throw new RangeError("ProgressBar value must be a finite number.");
  }
  return Math.max(0, Math.min(100, value));
}

export function ProgressBar({ value, label, className }: ProgressBarProps) {
  const percentage = clampProgress(value);
  return (
    <div className={cn("min-w-0 flex-1 space-y-2", className)} role="status">
      <div className="flex justify-between gap-3 text-sm text-fg-dim">
        <span>{label}</span>
        <span>{percentage}%</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-bg-3"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        aria-label={label}
      >
        <div
          className="h-full bg-brand motion-safe:transition-[width] motion-reduce:transition-none"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
