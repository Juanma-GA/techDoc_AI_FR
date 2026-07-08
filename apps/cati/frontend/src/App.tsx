import { ThemeToggle } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { Architecture } from "./routes/Architecture";
import { Data } from "./routes/Data";
import { Home } from "./routes/Home";
import { Import } from "./routes/Import";
import { Profiles } from "./routes/Profiles";
import { Settings } from "./routes/Settings";
import { Table } from "./routes/Table";

const navItems = [
  { to: "/", labelKey: "nav.home" },
  { to: "/import", labelKey: "nav.import" },
  { to: "/table", labelKey: "nav.table" },
  { to: "/profiles", labelKey: "nav.profiles" },
  { to: "/architecture", labelKey: "nav.architecture" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);

  return (
    <div className="flex h-screen bg-bg font-sans text-base text-fg">
      <aside className="flex w-64 flex-col gap-4 border-r border-md bg-card p-4">
        <div className="flex items-center justify-between">
          <span className="font-display text-lg tracking-wide text-brand-blue-light">CATI</span>
          <ThemeToggle />
        </div>
        <span className="label">v{t("app.version")}</span>

        <LlmBadge />

        <nav className="flex flex-col gap-1">
          {navItems.map(({ to, labelKey }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "rounded-sm px-3 py-2 text-sm transition-colors",
                  isActive ? "bg-card-hover text-fg" : "text-fg-dim hover:bg-card-hover hover:text-fg",
                ].join(" ")
              }
            >
              {t(labelKey)}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto flex gap-1" role="group" aria-label="Language">
          {LANGS.map((lng) => (
            <button
              key={lng}
              type="button"
              className={[
                "rounded-sm border border-md px-2 py-1 font-mono text-label uppercase",
                currentLang === lng ? "bg-card-hover text-fg" : "text-fg-dim hover:text-fg",
              ].join(" ")}
              onClick={() => void i18n.changeLanguage(lng)}
            >
              {lng}
            </button>
          ))}
        </div>
      </aside>

      <main className="flex-1 overflow-auto p-6">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/import" element={<Import />} />
            <Route path="/table" element={<Table />} />
            <Route path="/profiles" element={<Profiles />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}
