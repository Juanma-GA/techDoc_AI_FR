import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import { Dashboard } from "./routes/Dashboard";
import { Data } from "./routes/Data";
import { Documents } from "./routes/Documents";
import { Review } from "./routes/Review";
import { Rules } from "./routes/Rules";
import { Settings } from "./routes/Settings";

const navItems = [
  { to: "/", labelKey: "nav.dashboard" },
  { to: "/documents", labelKey: "nav.documents" },
  { to: "/rules", labelKey: "nav.rules" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);

  return (
    <div className="dw">
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="brand">Word-Reviewer</span>
            <span className="label">v{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          <LlmBadge />

          <nav>
            {navItems.map(({ to, labelKey }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
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
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/review/:docId" element={<Review />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
