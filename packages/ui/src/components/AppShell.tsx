import type { ReactNode } from "react";

import { cn } from "../lib/utils";
import { ThemeToggle } from "./ThemeToggle";
import "./app-shell.css";

export type AppShellProps = {
  title: ReactNode;
  version?: string;
  brandTitle?: string;
  navigation: ReactNode;
  navigationLabel?: string;
  /** Translated aria-label for the sidebar theme toggle. AppShell has no
   * language of its own — pass the caller's i18next-translated string, or
   * the English default renders regardless of the app's current locale. */
  themeToggleLabel?: string;
  llmStatus?: ReactNode;
  headerStart?: ReactNode;
  sidebarTop?: ReactNode;
  sidebarBottom?: ReactNode;
  languageSwitcher?: ReactNode;
  className?: string;
  mainClassName?: string;
  children: ReactNode;
};

export function AppShell({
  title,
  version,
  brandTitle,
  navigation,
  navigationLabel = "Main navigation",
  themeToggleLabel,
  llmStatus,
  headerStart,
  sidebarTop,
  sidebarBottom,
  languageSwitcher,
  className,
  mainClassName,
  children,
}: AppShellProps) {
  const normalizedVersion = version ? `v${version.replace(/^v/i, "")}` : null;

  return (
    <div className={cn("ui-app-shell", className)}>
      <aside className="ui-sidebar w-sidebar-w">
        <header className="ui-sidebar-header">
          {headerStart}
          <div className="ui-sidebar-heading">
            <span className="ui-sidebar-brand" title={brandTitle}>
              {title}
            </span>
            {normalizedVersion ? (
              <span className="ui-sidebar-version">{normalizedVersion}</span>
            ) : null}
          </div>
          <ThemeToggle
            className="ui-sidebar-theme-toggle h-[28px] w-[28px]"
            aria-label={themeToggleLabel}
          />
        </header>

        {sidebarTop}
        {llmStatus}
        <nav className="ui-sidebar-nav" aria-label={navigationLabel}>
          {navigation}
        </nav>
        {sidebarBottom}
        {languageSwitcher}
      </aside>

      <main className={cn("ui-main", mainClassName)}>{children}</main>
    </div>
  );
}

export function sidebarNavItemClass(isActive: boolean): string {
  return cn("ui-nav-item", isActive && "ui-nav-item-active");
}