import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import { setAppLanguage } from "./i18n";
import { Architecture } from "./routes/Architecture";
import { Chatbot } from "./routes/Chatbot";
import { Data } from "./routes/Data";
import { Manager } from "./routes/Manager";
import { ProjectDetail } from "./routes/ProjectDetail";
import { Projects } from "./routes/Projects";
import { Redacteur } from "./routes/Redacteur";
import { Settings } from "./routes/Settings";

// Coquille pixel-identique au preview.html (.layout / .sidebar / .nav-item /
// .lang-switch dans styles/preview-skin.css). Pas de logos sur les onglets.
const navItems = [
  { to: "/", labelKey: "nav.manager" },
  { to: "/projects", labelKey: "nav.projects" },
  { to: "/redacteur", labelKey: "nav.redacteur" },
  { to: "/chatbot", labelKey: "nav.chatbot" },
  { to: "/architecture", labelKey: "nav.architecture" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);

  return (
    <div className="ca">
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="brand" title={t("app.titleTooltip")}>
              {t("app.title")}
            </span>
            <span className="label">{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          <LlmBadge />

          <nav>
            {navItems.map(({ to, labelKey }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
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
                onClick={() => void setAppLanguage(lng)}
              >
                {lng.toUpperCase()}
              </button>
            ))}
          </div>
        </aside>

        <main>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Manager />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/projects/:id" element={<ProjectDetail />} />
              <Route path="/redacteur" element={<Redacteur />} />
              <Route path="/chatbot" element={<Chatbot />} />
              <Route path="/architecture" element={<Architecture />} />
              <Route path="/data" element={<Data />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
