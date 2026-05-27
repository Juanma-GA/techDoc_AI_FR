import { cva, type VariantProps } from "class-variance-authority";
import { type SelectHTMLAttributes, forwardRef } from "react";

import { cn } from "../lib/utils";

const selectVariants = cva(
  [
    "block w-full rounded-sm border bg-bg-2 px-3 text-fg",
    "appearance-none bg-no-repeat bg-right pr-8",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light",
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
        error: "border-danger",
      },
    },
    defaultVariants: {
      size: "md",
      state: "default",
    },
  },
);

export type SelectOption = { value: string; label: string };

export type SelectProps = Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "size"
> &
  VariantProps<typeof selectVariants> & {
    options: SelectOption[];
  };

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, size, state, options, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(selectVariants({ size, state }), className)}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export { selectVariants };
