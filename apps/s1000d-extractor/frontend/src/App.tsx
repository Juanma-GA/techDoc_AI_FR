import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import { Data } from "./routes/Data";
import { Migration } from "./routes/Migration";
import { Settings } from "./routes/Settings";
import { Versioning } from "./routes/Versioning";

const navItems = [
  { to: "/migration", labelKey: "nav.migration" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
  { to: "/versioning", labelKey: "nav.versioning" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const currentLang = (i18n.language || "fr").slice(0, 2);
  const showMigration = location.pathname === "/migration";

  return (
    <div className="dw">
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="brand">S1000D Extractor</span>
            <span className="label">v{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          <LlmBadge />

          <nav>
            {navItems.map(({ to, labelKey }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  isActive ? "nav-item active" : "nav-item"
                }
              >
                {t(labelKey)}
              </NavLink>
            ))}
          </nav>

          <div className="lang-switch" role="group" aria-label="Language">
            {LANGS.map((lng) => (
              <button
                key={lng}
                type="button"
                className={currentLang === lng ? "lang-btn active" : "lang-btn"}
                onClick={() => void i18n.changeLanguage(lng)}
              >
                {lng.toUpperCase()}
              </button>
            ))}
          </div>
        </aside>

        <main>
          <div hidden={!showMigration}>
            <Migration />
          </div>
          <Routes>
            <Route path="/" element={<Navigate to="/migration" replace />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/versioning" element={<Versioning />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
