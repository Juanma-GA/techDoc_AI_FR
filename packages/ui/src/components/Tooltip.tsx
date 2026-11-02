import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import {
  type ComponentPropsWithoutRef,
  type ElementRef,
  type ReactNode,
  forwardRef,
} from "react";

import { cn } from "../lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;
export const TooltipRoot = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = forwardRef<
  ElementRef<typeof TooltipPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 max-w-xs rounded-sm border bg-card px-2.5 py-1.5 text-xs text-fg shadow-popover",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";

export type TooltipProps = {
  /** Translated tooltip text. Icon-only triggers still need their own aria-label. */
  content: ReactNode;
  children: ReactNode;
  side?: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>["side"];
  delayDuration?: number;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
};

/**
 * Hover/focus tooltip. `children` must be a single focusable element
 * (rendered with `asChild`). Includes its own provider so it works anywhere.
 */
export function Tooltip({
  content,
  children,
  side = "top",
  delayDuration = 300,
  open,
  defaultOpen,
  onOpenChange,
}: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={delayDuration}>
      <TooltipPrimitive.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipContent side={side}>{content}</TooltipContent>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
