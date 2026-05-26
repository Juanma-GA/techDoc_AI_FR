import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { type ReactNode } from "react";

import { cn } from "../lib/utils";

type DeltaDirection = "up" | "down" | "stable";

export type KpiDelta = {
  direction: DeltaDirection;
  label?: string;
};

export type KpiCardProps = {
  label: string;
  value: ReactNode;
  delta?: KpiDelta;
  className?: string;
};

const DELTA_ICON = {
  up: TrendingUp,
  down: TrendingDown,
  stable: Minus,
} as const;

const DELTA_COLOR: Record<DeltaDirection, string> = {
  up: "text-success",
  down: "text-danger",
  stable: "text-fg-dim",
};

function DeltaRow({ delta }: { delta: KpiDelta }) {
  const Icon = DELTA_ICON[delta.direction];
  return (
    <div className={cn("mt-1 flex items-center gap-1 text-xs", DELTA_COLOR[delta.direction])}>
      <Icon size={12} aria-hidden="true" />
      {delta.label ? <span>{delta.label}</span> : null}
    </div>
  );
}

export function KpiCard({ label, value, delta, className }: KpiCardProps) {
  return (
    <div className={cn("rounded-lg border bg-card p-4 shadow-card", className)}>
      <div className="text-label font-mono uppercase text-fg-dim">{label}</div>
      <div className="mt-2 font-mono text-2xl font-bold text-fg">{value}</div>
      {delta ? <DeltaRow delta={delta} /> : null}
    </div>
  );
}
