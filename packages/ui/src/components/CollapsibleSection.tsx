import { ChevronDown } from "lucide-react";
import { type ReactNode, useId, useState } from "react";

import { cn } from "../lib/utils";

export type CollapsibleSectionProps = {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  /** Uncontrolled initial state (default: open). */
  defaultOpen?: boolean;
  /** Controlled state; pair with `onOpenChange`. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Extra content shown in the header, right side (badge, status). */
  aside?: ReactNode;
  className?: string;
};

/**
 * Card-like section with an accessible disclosure button (`aria-expanded`,
 * `aria-controls`). Used for the LLM settings block (collapsed once configured)
 * and any optional/advanced form area.
 */
export function CollapsibleSection({
  title,
  description,
  children,
  defaultOpen = true,
  open,
  onOpenChange,
  aside,
  className,
}: CollapsibleSectionProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const isOpen = open ?? internalOpen;
  const contentId = useId();

  const toggle = () => {
    const next = !isOpen;
    if (open === undefined) setInternalOpen(next);
    onOpenChange?.(next);
  };

  return (
    <section className={cn("rounded-lg border bg-card shadow-card", className)}>
      <div className="flex items-center gap-3 p-4">
        <button
          type="button"
          aria-expanded={isOpen}
          aria-controls={contentId}
          onClick={toggle}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-2 rounded-sm text-left",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
          )}
        >
          <ChevronDown
            size={16}
            aria-hidden="true"
            className={cn(
              "shrink-0 text-fg-dim transition-transform duration-base motion-reduce:transition-none",
              !isOpen && "-rotate-90",
            )}
          />
          <span className="min-w-0">
            <span className="block font-display text-card-title text-fg">{title}</span>
            {description ? <span className="mt-0.5 block text-sm text-fg-dim">{description}</span> : null}
          </span>
        </button>
        {aside ? <div className="shrink-0">{aside}</div> : null}
      </div>
      <div id={contentId} hidden={!isOpen} className="border-t p-4">
        {children}
      </div>
    </section>
  );
}
