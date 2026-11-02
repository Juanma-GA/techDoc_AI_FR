import { cva, type VariantProps } from "class-variance-authority";
import { type TextareaHTMLAttributes, forwardRef } from "react";

import { cn } from "../lib/utils";

const textareaVariants = cva(
  [
    "block w-full rounded-sm border bg-surface-sunken px-3 py-2 text-fg",
    "placeholder:text-fg-muted",
    "transition-colors duration-fast focus-visible:outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-focus/40",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "resize-y",
  ].join(" "),
  {
    variants: {
      state: {
        default: "border-md",
        error: "border-danger focus-visible:border-danger focus-visible:ring-danger/30",
      },
    },
    defaultVariants: {
      state: "default",
    },
  },
);

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> &
  VariantProps<typeof textareaVariants>;

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, state, rows = 4, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(textareaVariants({ state }), className)}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export { textareaVariants };
