import { ThemeToggle } from "@internal/ui";
import {
  FolderKanban,
  LayoutDashboard,
  type LucideIcon,
  MessageSquare,
  Settings as SettingsIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Chat } from "./routes/Chat";
import { Dashboard } from "./routes/Dashboard";
import { Projects } from "./routes/Projects";
import { Settings } from "./routes/Settings";

type NavItem = { to: string; icon: LucideIcon; labelKey: string };

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { to: "/", icon: LayoutDashboard, labelKey: "nav.dashboard" },
  { to: "/projects", icon: FolderKanban, labelKey: "nav.projects" },
  { to: "/chat", icon: MessageSquare, labelKey: "nav.chat" },
  { to: "/settings", icon: SettingsIcon, labelKey: "nav.settings" },
];

function Sidebar() {
  const { t } = useTranslation();
  return (
    <aside
      aria-label={t("nav.section")}
      className="flex w-sidebar-w shrink-0 flex-col border-r bg-bg-2"
    >
      <header className="flex items-baseline gap-2 border-b px-4 py-4">
        <span
          className="font-display text-lg text-brand-blue-light"
          title={t("app.titleTooltip")}
        >
          {t("app.title")}
        </span>
        <span className="label">{t("app.version")}</span>
      </header>
      <nav className="flex flex-col gap-1 p-3">
        {NAV_ITEMS.map(({ to, icon: Icon, labelKey }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-sm px-3 py-2 transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light",
                isActive
                  ? "bg-brand text-fg"
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
  );
}

export function App() {
  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-bg font-sans text-base text-fg">
        <Sidebar />
        <main className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-topbar-h items-center justify-end gap-2 border-b px-4">
            <ThemeToggle />
          </header>
          <div className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
