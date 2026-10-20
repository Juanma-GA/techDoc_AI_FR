import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState, type ReactNode } from "react";

import { useMediaQuery } from "../hooks/useMediaQuery";
import { cn } from "../lib/utils";
import { ThemeToggle } from "./ThemeToggle";
import "./app-shell.css";
import "./app-shell-sidebar.css";

export type AppShellProps = {
  title: ReactNode;
  version?: string;
  brandTitle?: string;
  navigation: ReactNode;
  navigationLabel?: string;
  collapsible?: boolean;
  collapseLabel?: string;
  expandLabel?: string;
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
  collapsible = false,
  collapseLabel = "Collapse sidebar",
  expandLabel = "Expand sidebar",
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
  const [collapsed, setCollapsed] = useState(false);
  const isMobile = useMediaQuery("(max-width: 760px)");
  const isCollapsed = collapsible && collapsed && !isMobile;
  const toggleLabel = isCollapsed ? expandLabel : collapseLabel;
  const normalizedVersion = version ? `v${version.replace(/^v/i, "")}` : null;

  return (
    <div className={cn("ui-app-shell", className)}>
      <aside
        className={cn(
          "ui-sidebar",
          collapsible && "ui-sidebar-collapsible",
          isCollapsed ? "w-16 ui-sidebar-collapsed" : "w-sidebar-w",
        )}
        data-collapsed={isCollapsed}
      >
        <header className="ui-sidebar-header">
          {headerStart ? <div className="ui-sidebar-brand-start">{headerStart}</div> : null}
          <div className="ui-sidebar-heading">
            <span className="ui-sidebar-brand" title={brandTitle}>
              {title}
            </span>
            {normalizedVersion ? (
              <span className="ui-sidebar-version">{normalizedVersion}</span>
            ) : null}
          </div>
          {collapsible && !isMobile ? (
            <button
              type="button"
              className="ui-sidebar-collapse-toggle"
              aria-label={toggleLabel}
              aria-expanded={!isCollapsed}
              title={toggleLabel}
              onClick={() => setCollapsed((value) => !value)}
            >
              {isCollapsed ? (
                <PanelLeftOpen size={18} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={18} aria-hidden="true" />
              )}
            </button>
          ) : null}
          <ThemeToggle
            className="ui-sidebar-theme-toggle h-[28px] w-[28px]"
            aria-label={themeToggleLabel}
          />
        </header>

        {sidebarTop ? (
          <div className="ui-sidebar-collapse-auxiliary">{sidebarTop}</div>
        ) : null}
        {llmStatus ? (
          <div className="ui-sidebar-collapse-auxiliary">{llmStatus}</div>
        ) : null}
        <nav className="ui-sidebar-nav" aria-label={navigationLabel}>
          {navigation}
        </nav>
        {sidebarBottom ? (
          <div className="ui-sidebar-collapse-auxiliary">{sidebarBottom}</div>
        ) : null}
        {languageSwitcher}
      </aside>

      <main className={cn("ui-main", mainClassName)}>{children}</main>
    </div>
  );
}

export function sidebarNavItemClass(isActive: boolean): string {
  return cn("ui-nav-item", isActive && "ui-nav-item-active");
}