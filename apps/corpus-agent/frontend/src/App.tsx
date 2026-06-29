import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import { setAppLanguage } from "./i18n";

// Routes chargees en lazy (code-splitting) : chaque onglet devient un chunk
// separe, charge a la navigation. Reduit le bundle initial / le TTI : on ne
// telecharge Settings/Chatbot/etc. que quand l'utilisateur y va. Les exports
// sont nommes -> on les mappe sur `default` attendu par React.lazy.
const Manager = lazy(() => import("./routes/Manager").then((m) => ({ default: m.Manager })));
const Projects = lazy(() => import("./routes/Projects").then((m) => ({ default: m.Projects })));
const ProjectDetail = lazy(() =>
  import("./routes/ProjectDetail").then((m) => ({ default: m.ProjectDetail })),
);
const Redacteur = lazy(() => import("./routes/Redacteur").then((m) => ({ default: m.Redacteur })));
const Chatbot = lazy(() => import("./routes/Chatbot").then((m) => ({ default: m.Chatbot })));
const Architecture = lazy(() =>
  import("./routes/Architecture").then((m) => ({ default: m.Architecture })),
);
const Data = lazy(() => import("./routes/Data").then((m) => ({ default: m.Data })));
const Settings = lazy(() => import("./routes/Settings").then((m) => ({ default: m.Settings })));

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
            <Suspense fallback={<div className="empty-state">{t("common.loading")}</div>}>
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
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
