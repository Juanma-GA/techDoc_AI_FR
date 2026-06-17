// Shell applicatif : sidebar (navigation + switcher de langue FR/EN), topbar
// (theme toggle) et routes. La navigation et les libelles consomment le bundle
// i18n du backend (memes cles que la preview HTML) — cf. i18n.ts.
import { Button, ThemeToggle } from "@internal/ui";
import {
  ClipboardList,
  Database,
  FolderKanban,
  LayoutDashboard,
  type LucideIcon,
  MessageSquare,
  Network,
  Settings as SettingsIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { setAppLanguage, SUPPORTED_LANGS } from "./i18n";
import { Architecture } from "./routes/Architecture";
import { Chat } from "./routes/Chat";
import { Data } from "./routes/Data";
import { Dashboard } from "./routes/Dashboard";
import { Projects } from "./routes/Projects";
import { Redacteur } from "./routes/Redacteur";
import { Settings } from "./routes/Settings";

type NavItem = { to: string; icon: LucideIcon; labelKey: string };

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { to: "/", icon: LayoutDashboard, labelKey: "nav.manager" },
  { to: "/projects", icon: FolderKanban, labelKey: "nav.projects" },
  { to: "/redacteur", icon: ClipboardList, labelKey: "nav.redacteur" },
  { to: "/architecture", icon: Network, labelKey: "nav.architecture" },
  { to: "/data", icon: Database, labelKey: "nav.data" },
  { to: "/chat", icon: MessageSquare, labelKey: "nav.chatbot" },
  { to: "/settings", icon: SettingsIcon, labelKey: "nav.settings" },
];

function LangSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.language?.startsWith("en") ? "en" : "fr";
  return (
    <div className="mt-auto flex gap-2 border-t p-3" role="group" aria-label="Language">
      {SUPPORTED_LANGS.map((lng) => (
        <Button
          key={lng}
          variant={current === lng ? "primary" : "ghost"}
          size="sm"
          className="flex-1 uppercase"
          aria-pressed={current === lng}
          onClick={() => void setAppLanguage(lng)}
        >
          {lng}
        </Button>
      ))}
    </div>
  );
}

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
      <LangSwitcher />
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
              <Route path="/redacteur" element={<Redacteur />} />
              <Route path="/architecture" element={<Architecture />} />
              <Route path="/data" element={<Data />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
