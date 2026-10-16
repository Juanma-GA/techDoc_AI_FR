import type { ReactNode } from "react";

import { ThemeToggle } from "./ThemeToggle";
import "./app-shell.css";

export type AppShellProps = {
  title: ReactNode;
  version?: string;
  brandTitle?: string;
  navigation: ReactNode;
  navigationLabel?: string;
  themeToggleLabel?: string;
  languageSwitcher?: ReactNode;
  children: ReactNode;
};

export function AppShell({
  title,
  version,
  brandTitle,
  navigation,
  navigationLabel = "Main navigation",
  themeToggleLabel,
  languageSwitcher,
  children,
}: AppShellProps) {
  const normalizedVersion = version ? `v${version.replace(/^v/i, "")}` : null;

  return (
    <div className="ui-app-shell">
      <aside className="ui-sidebar">
        <header className="ui-sidebar-header">
          <div className="ui-sidebar-heading">
            <span className="ui-sidebar-brand" title={brandTitle}>
              {title}
            </span>
            {normalizedVersion ? (
              <span className="ui-sidebar-version">{normalizedVersion}</span>
            ) : null}
          </div>
          <ThemeToggle
            className="ui-sidebar-theme-toggle"
            aria-label={themeToggleLabel}
          />
        </header>

        <nav className="ui-sidebar-nav" aria-label={navigationLabel}>
          {navigation}
        </nav>
        {languageSwitcher}
      </aside>

      <main className="ui-main">{children}</main>
    </div>
  );
}

export function sidebarNavItemClass(isActive: boolean): string {
  return `ui-nav-item${isActive ? " ui-nav-item-active" : ""}`;
}
