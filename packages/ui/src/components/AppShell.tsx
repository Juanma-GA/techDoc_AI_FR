import {
  ArrowLeftRight,
  CircleAlert,
  Database,
  FileText,
  Files,
  FolderOpen,
  GitBranch,
  House,
  ListChecks,
  MessageSquare,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  ScanLine,
  Settings as SettingsIcon,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { useMediaQuery } from "../hooks/useMediaQuery";
import { cn } from "../lib/utils";
import { Ai4TechDocLogo } from "./Ai4TechDocLogo";
import { ThemeToggle } from "./ThemeToggle";
import "./app-shell.css";
import "./app-shell-sidebar.css";

export type AppShellProps = {
  title: ReactNode;
  brandTitle?: string;
  navigation: ReactNode;
  navigationLabel?: string;
  collapseLabel?: string;
  expandLabel?: string;
  /** Translated aria-label for the sidebar theme toggle. AppShell has no
   * language of its own — pass the caller's i18next-translated string, or
   * the English default renders regardless of the app's current locale. */
  themeToggleLabel?: string;
  llmStatus?: ReactNode;
  sidebarTop?: ReactNode;
  sidebarContent?: ReactNode;
  sidebarBottom?: ReactNode;
  languageSwitcher?: ReactNode;
  className?: string;
  mainClassName?: string;
  children: ReactNode;
};

export function AppShell({
  title,
  brandTitle,
  navigation,
  navigationLabel = "Main navigation",
  collapseLabel = "Collapse sidebar",
  expandLabel = "Expand sidebar",
  themeToggleLabel,
  llmStatus,
  sidebarTop,
  sidebarContent,
  sidebarBottom,
  languageSwitcher,
  className,
  mainClassName,
  children,
}: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const isMobile = useMediaQuery("(max-width: 760px)");
  const isCollapsed = collapsed && !isMobile;
  const toggleLabel = isCollapsed ? expandLabel : collapseLabel;

  return (
    <div className={cn("ui-app-shell", className)}>
      <aside
        className={cn(
          "ui-sidebar ui-sidebar-collapsible",
          isCollapsed ? "ui-sidebar-collapsed" : "ui-sidebar-expanded",
        )}
        data-testid="sidebar"
        data-collapsed={isCollapsed}
        data-has-content={Boolean(sidebarContent)}
      >
        <header className="ui-sidebar-header">
          <div className="ui-sidebar-brand-start"><Ai4TechDocLogo alt="" /></div>
          <div className="ui-sidebar-heading">
            <span className="ui-sidebar-brand" title={brandTitle}>
              {title}
            </span>
          </div>
          {!isMobile ? (
            <button
              type="button"
              className="ui-sidebar-collapse-toggle"
              aria-label={toggleLabel}
              aria-expanded={!isCollapsed}
              title={toggleLabel}
              data-testid="sidebar-toggle"
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
            className="ui-sidebar-theme-toggle"
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
        {sidebarContent ? (
          <div className="ui-sidebar-content ui-sidebar-collapse-auxiliary">{sidebarContent}</div>
        ) : null}
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

export type SidebarNavContentProps = {
  icon: SidebarNavIconName | LucideIcon;
  label: ReactNode;
};

export type SidebarNavIconName =
  | "home"
  | "file"
  | "files"
  | "data"
  | "settings"
  | "workflow"
  | "project"
  | "chat"
  | "review"
  | "rules"
  | "scan"
  | "templates"
  | "migration"
  | "versioning"
  | "compare"
  | "convert"
  | "tree"
  | "color"
  | "rename"
  | "replacement"
  | "quality"
  | "editor";

const NAV_ICONS: Record<SidebarNavIconName, LucideIcon> = {
  home: House,
  file: FileText,
  files: Files,
  data: Database,
  settings: SettingsIcon,
  workflow: Workflow,
  project: FolderOpen,
  chat: MessageSquare,
  review: CircleAlert,
  rules: ListChecks,
  scan: ScanLine,
  templates: Files,
  migration: GitBranch,
  versioning: GitBranch,
  compare: ArrowLeftRight,
  convert: ArrowLeftRight,
  tree: Workflow,
  color: Palette,
  rename: Pencil,
  replacement: ArrowLeftRight,
  quality: ListChecks,
  editor: Workflow,
};

export function SidebarNavContent({ icon, label }: SidebarNavContentProps) {
  const Icon = typeof icon === "string" ? NAV_ICONS[icon] : icon;
  return (
    <>
      <span className="ui-nav-icon" aria-hidden="true"><Icon size={16} /></span>
      <span className="ui-nav-label">{label}</span>
    </>
  );
}