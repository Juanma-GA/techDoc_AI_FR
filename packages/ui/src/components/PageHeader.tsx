import { type HTMLAttributes, type ReactNode, forwardRef } from "react";

import { cn } from "../lib/utils";

export type PageHeaderProps = Omit<HTMLAttributes<HTMLElement>, "title"> & {
  title: ReactNode;
  description?: ReactNode;
  /** Small uppercase label above the title (section, breadcrumb, context). */
  eyebrow?: ReactNode;
  /** Buttons or controls aligned to the right on desktop, wrapped below on mobile. */
  actions?: ReactNode;
};

/**
 * Standard page heading: Orbitron title, dimmed description, right-aligned
 * actions. Keeps the legacy `page-header` / `page-header-actions` class names
 * so existing app CSS and tests still match.
 */
export const PageHeader = forwardRef<HTMLElement, PageHeaderProps>(
  ({ title, description, eyebrow, actions, className, ...props }, ref) => (
    <header
      ref={ref}
      className={cn("page-header mb-6 flex flex-wrap items-start justify-between gap-4", className)}
      {...props}
    >
      <div className="min-w-0 flex-1">
        {eyebrow ? <div className="label mb-1">{eyebrow}</div> : null}
        <h1 className="m-0 font-display text-page-title text-fg">{title}</h1>
        {description ? <p className="m-0 mt-1 max-w-3xl text-fg-dim">{description}</p> : null}
      </div>
      {actions ? (
        <div className="page-header-actions flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  ),
);
PageHeader.displayName = "PageHeader";
