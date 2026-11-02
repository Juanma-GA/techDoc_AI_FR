import { forwardRef } from "react";

import { cn } from "../lib/utils";

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
  /** Accessible label when no visible label wraps the switch. */
  "aria-label"?: string;
  className?: string;
}

/**
 * Toggle on/off accessible (role=switch). Bascule immediate — pas une action
 * destructrice, donc pas de confirmation. Stylé via les design-tokens.
 */
export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked, onCheckedChange, disabled, id, className, ...props }, ref) => (
    <button
      ref={ref}
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "border-brand bg-brand" : "border-md bg-bg-3",
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 rounded-full transition-transform",
          checked ? "translate-x-[22px] bg-brand-fg" : "translate-x-[3px] bg-fg-dim",
        )}
      />
    </button>
  ),
);
Switch.displayName = "Switch";
