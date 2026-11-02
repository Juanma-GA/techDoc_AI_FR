import { cva, type VariantProps } from "class-variance-authority";
import { type InputHTMLAttributes, forwardRef } from "react";

import { cn } from "../lib/utils";

const inputVariants = cva(
  [
    "block w-full rounded-sm border bg-surface-sunken px-3 text-fg",
    "placeholder:text-fg-muted",
    "transition-colors duration-fast focus-visible:outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-focus/40",
    "disabled:cursor-not-allowed disabled:opacity-50",
  ].join(" "),
  {
    variants: {
      size: {
        sm: "h-8 text-sm",
        md: "h-10",
        lg: "h-11 text-base",
      },
      state: {
        default: "border-md",
        error: "border-danger focus-visible:border-danger focus-visible:ring-danger/30",
      },
    },
    defaultVariants: {
      size: "md",
      state: "default",
    },
  },
);

export type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "size"> &
  VariantProps<typeof inputVariants>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, size, state, type = "text", ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(inputVariants({ size, state }), className)}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { inputVariants };
