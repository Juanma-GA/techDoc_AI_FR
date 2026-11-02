import { type HTMLAttributes } from "react";

import { cn } from "../lib/utils";

/** Loading placeholder. Size it with utilities: `<Skeleton className="h-4 w-40" />`. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      data-testid="skeleton"
      className={cn("animate-pulse rounded-sm bg-bg-3 motion-reduce:animate-none", className)}
      {...props}
    />
  );
}
