import { forwardRef } from "react";

import { cn } from "../lib/utils";

export interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
  /** Accessible label when no visible label wraps the checkbox. */
  "aria-label"?: string;
  className?: string;
}

/**
 * Case a cocher accessible (role=checkbox). Selection multiple non destructrice
 * (ex. navigateur de fichiers). Stylée via les design-tokens.
 */
export const Checkbox = forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ checked, onCheckedChange, disabled, id, className, ...props }, ref) => (
    <button
      ref={ref}
      id={id}
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-light",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "border-brand bg-brand text-fg" : "border-border bg-bg-3",
        className,
      )}
      {...props}
    >
      {checked ? (
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
          <path
            d="M3.5 8.5l3 3 6-7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : null}
    </button>
  ),
);
Checkbox.displayName = "Checkbox";
