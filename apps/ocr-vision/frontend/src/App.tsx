import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import { Architecture } from "./routes/Architecture";
import { Data } from "./routes/Data";
import { Extraction } from "./routes/Extraction";
import { Home } from "./routes/Home";
import { Ocr } from "./routes/Ocr";
import { Settings } from "./routes/Settings";
import { Templates } from "./routes/Templates";

const navItems = [
  { to: "/", labelKey: "nav.ocr" },
  { to: "/extraction", labelKey: "nav.extraction" },
  { to: "/templates", labelKey: "nav.templates" },
  { to: "/home", labelKey: "nav.home" },
  { to: "/architecture", labelKey: "nav.architecture" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);

  return (
    <ErrorBoundary>
    <div className="dw">
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="brand">OCR Vision</span>
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
            <Route path="/" element={<Ocr />} />
            <Route path="/extraction" element={<Extraction />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/home" element={<Home />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
    </ErrorBoundary>
  );
}
