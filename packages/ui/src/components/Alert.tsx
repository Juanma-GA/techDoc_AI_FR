import { cva, type VariantProps } from "class-variance-authority";
import { AlertTriangle, CheckCircle2, Info, XCircle, type LucideIcon } from "lucide-react";
import { type HTMLAttributes, type ReactNode, forwardRef } from "react";

import { cn } from "../lib/utils";

const alertVariants = cva("flex items-start gap-3 rounded-lg border p-3 text-sm text-fg", {
  variants: {
    variant: {
      info: "border-info/30 bg-info/10",
      success: "border-success/30 bg-success/10",
      warning: "border-warning/30 bg-warning/10",
      danger: "border-danger/30 bg-danger/10",
    },
  },
  defaultVariants: { variant: "info" },
});

const ICONS: Record<NonNullable<AlertProps["variant"]>, { icon: LucideIcon; color: string }> = {
  info: { icon: Info, color: "text-info" },
  success: { icon: CheckCircle2, color: "text-success" },
  warning: { icon: AlertTriangle, color: "text-warning" },
  danger: { icon: XCircle, color: "text-danger" },
};

export type AlertProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> &
  VariantProps<typeof alertVariants> & {
    title?: ReactNode;
    /** Replace the default variant icon; pass `null` to hide it. */
    icon?: LucideIcon | null;
  };

/**
 * Inline banner (callout) for page-level information, warnings or errors.
 * `danger` uses role="alert" (announced immediately), others role="status".
 */
export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant, title, icon, children, role, ...props }, ref) => {
    const resolved = variant ?? "info";
    const Icon = icon === undefined ? ICONS[resolved].icon : icon;
    return (
      <div
        ref={ref}
        role={role ?? (resolved === "danger" ? "alert" : "status")}
        className={cn(alertVariants({ variant: resolved }), className)}
        {...props}
      >
        {Icon ? (
          <Icon size={16} className={cn("mt-0.5 shrink-0", ICONS[resolved].color)} aria-hidden="true" />
        ) : null}
        <div className="min-w-0 flex-1">
          {title ? <div className="font-semibold">{title}</div> : null}
          {children ? <div className={cn(title ? "mt-0.5 text-fg-dim" : undefined)}>{children}</div> : null}
        </div>
      </div>
    );
  },
);
Alert.displayName = "Alert";

export { alertVariants };
