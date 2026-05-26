import { Loader2 } from "lucide-react";

import { cn } from "../lib/utils";

export type LoadingOverlayProps = {
  visible: boolean;
  label?: string;
  className?: string;
};

export function LoadingOverlay({ visible, label = "Chargement…", className }: LoadingOverlayProps) {
  if (!visible) {
    return null;
  }
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        "absolute inset-0 z-50 flex items-center justify-center gap-3 bg-bg/70 backdrop-blur-sm",
        className,
      )}
    >
      <Loader2 className="animate-spin text-brand-blue-light" size={28} aria-hidden="true" />
      <span className="font-mono text-fg-dim">{label}</span>
    </div>
  );
}
