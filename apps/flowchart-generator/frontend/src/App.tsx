import { DemoModeBadge, DemoModeProvider, ErrorBoundary, Spinner, ThemeToggle, cn } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { Database, PanelLeftClose, PanelLeftOpen, Settings as SettingsIcon, Workflow } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { LangSwitch } from "./components/LangSwitch";
import { LlmBadge } from "./components/LlmBadge";
import { settingsApi } from "./lib/api";

const Editor = lazy(() => import("./routes/Editor").then((m) => ({ default: m.Editor })));
const Data = lazy(() => import("./routes/Data").then((m) => ({ default: m.Data })));
const Settings = lazy(() => import("./routes/Settings").then((m) => ({ default: m.Settings })));

const NAV = [
  { to: "/editor", key: "nav.editor", icon: Workflow },
  { to: "/data", key: "nav.data", icon: Database },
  { to: "/settings", key: "nav.settings", icon: SettingsIcon },
];

export function App() {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const toggleLabel = collapsed ? t("nav.expand") : t("nav.collapse");
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: settingsApi.read });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  return (
    <div className="flex h-screen bg-bg font-sans text-base text-fg">
      <aside
        className={cn(
          "flex shrink-0 flex-col gap-4 border-r bg-bg-2 py-4 transition-[width]",
          collapsed ? "w-16 items-center px-2" : "w-56 px-4",
        )}
        data-testid="sidebar"
        data-collapsed={collapsed}
      >
        <div className={cn("flex gap-2", collapsed ? "flex-col items-center" : "items-start justify-between")}>
          {!collapsed && (
            <div title={t("app.description")} style={{ cursor: "help" }}>
              <div className="font-display text-lg leading-tight text-brand-blue-light">{t("app.title")}</div>
            </div>
          )}
          <button
            type="button"
            className="rounded p-1 text-fg-dim hover:bg-card-hover hover:text-fg"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={toggleLabel}
            aria-expanded={!collapsed}
            title={toggleLabel}
            data-testid="sidebar-toggle"
          >
            {collapsed ? <PanelLeftOpen size={18} aria-hidden /> : <PanelLeftClose size={18} aria-hidden />}
          </button>
        </div>
        <LlmBadge compact={collapsed} />
        {demoEnabled && !collapsed && <DemoModeBadge label={t("demo.badge")} />}
        <nav className="flex w-full flex-col gap-1">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={t(key)}
              aria-label={t(key)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded py-2 text-sm hover:bg-card-hover",
                  collapsed ? "justify-center px-0" : "px-3",
                  isActive ? "bg-card text-fg" : "text-fg-dim",
                )
              }
            >
              <Icon size={16} aria-hidden />
              {!collapsed && <span>{t(key)}</span>}
            </NavLink>
          ))}
        </nav>
        <div className={cn("mt-auto flex gap-2", collapsed ? "flex-col items-center" : "items-center justify-between")}>
          <LangSwitch vertical={collapsed} />
          <ThemeToggle />
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto p-6">
        <DemoModeProvider mode={demoEnabled ? "demo" : "normal"} isReady={settingsQuery.isSuccess}>
          <ErrorBoundary>
            <Suspense fallback={<Spinner />}>
              <Routes>
                <Route path="/" element={<Navigate to="/editor" replace />} />
                <Route path="/editor" element={<Editor />} />
                <Route path="/data" element={<Data />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/editor" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </DemoModeProvider>
      </main>
    </div>
  );
}
