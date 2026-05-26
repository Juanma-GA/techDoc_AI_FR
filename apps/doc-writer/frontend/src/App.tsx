import { ThemeToggle } from "@internal/ui";
import { FileText, History, Settings as SettingsIcon, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Documents } from "./routes/Documents";
import { Generate } from "./routes/Generate";
import { Sessions } from "./routes/Sessions";
import { Settings } from "./routes/Settings";

const navItems = [
  { to: "/", labelKey: "nav.generate", icon: Sparkles },
  { to: "/documents", labelKey: "nav.documents", icon: FileText },
  { to: "/sessions", labelKey: "nav.sessions", icon: History },
  { to: "/settings", labelKey: "nav.settings", icon: SettingsIcon },
] as const;

export function App() {
  const { t } = useTranslation();
  return (
    <div className="flex h-screen bg-bg font-sans text-base text-fg">
      <aside className="flex w-sidebar-w shrink-0 flex-col border-r bg-bg-2">
        <div className="flex h-topbar-h items-center px-4">
          <span className="font-display text-lg text-brand-blue-light">
            {t("app.title")}
          </span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-2">
          {navItems.map(({ to, labelKey, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-card text-fg"
                    : "text-fg-dim hover:bg-card-hover hover:text-fg",
                ].join(" ")
              }
            >
              <Icon size={16} aria-hidden="true" />
              <span>{t(labelKey)}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-topbar-h items-center justify-end border-b px-4">
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-auto p-6">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Generate />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/sessions" element={<Sessions />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
