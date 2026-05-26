import { Loader2 } from "lucide-react";

import { cn } from "../lib/utils";

const sizeMap = {
  sm: 14,
  md: 18,
  lg: 24,
} as const;

export type SpinnerProps = {
  size?: keyof typeof sizeMap;
  className?: string;
  "aria-label"?: string;
};

export function Spinner({ size = "md", className, ...rest }: SpinnerProps) {
  return (
    <Loader2
      size={sizeMap[size]}
      className={cn("animate-spin text-fg-dim", className)}
      role="status"
      aria-label={rest["aria-label"] ?? "Chargement"}
    />
  );
}
