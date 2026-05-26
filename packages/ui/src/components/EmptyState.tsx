import { type LucideProps } from "lucide-react";
import { type ComponentType, type ReactNode } from "react";

import { cn } from "../lib/utils";

export type EmptyStateProps = {
  icon?: ComponentType<LucideProps>;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border bg-card p-10 text-center shadow-card",
        className,
      )}
    >
      {Icon ? <Icon size={32} className="text-fg-muted" aria-hidden="true" /> : null}
      <h3 className="font-display text-lg text-fg">{title}</h3>
      {description ? <p className="max-w-md text-sm text-fg-dim">{description}</p> : null}
      {action}
    </div>
  );
}
