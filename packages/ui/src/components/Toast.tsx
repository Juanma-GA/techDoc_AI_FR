import * as ToastPrimitive from "@radix-ui/react-toast";
import { X } from "lucide-react";
import {
  type ComponentPropsWithoutRef,
  type ElementRef,
  forwardRef,
} from "react";

import { cn } from "../lib/utils";

/**
 * Use these everywhere instead of `alert()`. STANDARD §11.
 *
 * Wrap the app in <ToastProvider>, drop a <Toaster /> next to it, and
 * dispatch <Toast variant="success">…</Toast> from feature code.
 */

export const ToastProvider = ToastPrimitive.Provider;
export const ToastTitle = ToastPrimitive.Title;
export const ToastDescription = ToastPrimitive.Description;
export const ToastAction = ToastPrimitive.Action;

export const Toaster = forwardRef<
  ElementRef<typeof ToastPrimitive.Viewport>,
  ComponentPropsWithoutRef<typeof ToastPrimitive.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Viewport
    ref={ref}
    className={cn(
      "fixed bottom-0 right-0 z-50 flex max-h-screen w-full flex-col gap-2 p-4 sm:max-w-md",
      className,
    )}
    {...props}
  />
));
Toaster.displayName = "Toaster";

const TOAST_VARIANTS = {
  default: "border bg-card text-fg",
  success: "border-success/40 border-l-4 border-l-success bg-card text-success",
  warning: "border-warning/40 border-l-4 border-l-warning bg-card text-warning",
  danger: "border-danger/40 border-l-4 border-l-danger bg-card text-danger",
} as const;

export type ToastVariant = keyof typeof TOAST_VARIANTS;

export type ToastProps = ComponentPropsWithoutRef<typeof ToastPrimitive.Root> & {
  variant?: ToastVariant;
};

export const Toast = forwardRef<ElementRef<typeof ToastPrimitive.Root>, ToastProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <ToastPrimitive.Root
      ref={ref}
      className={cn(
        "flex items-start justify-between gap-3 rounded-lg border p-3 shadow-popover",
        TOAST_VARIANTS[variant],
        className,
      )}
      {...props}
    />
  ),
);
Toast.displayName = "Toast";

export const ToastClose = forwardRef<
  ElementRef<typeof ToastPrimitive.Close>,
  ComponentPropsWithoutRef<typeof ToastPrimitive.Close>
>(({ className, children, ...props }, ref) => (
  <ToastPrimitive.Close
    ref={ref}
    aria-label="Close"
    className={cn(
      "rounded-sm p-1 text-fg-dim hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
      className,
    )}
    {...props}
  >
    {children ?? <X size={14} aria-hidden="true" />}
  </ToastPrimitive.Close>
));
ToastClose.displayName = "ToastClose";
