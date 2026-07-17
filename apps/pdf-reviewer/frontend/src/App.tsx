import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import i18n from "./i18n";
import { Architecture } from "./routes/Architecture";
import { Dashboard } from "./routes/Dashboard";
import { Data } from "./routes/Data";
import { DocumentReviewer } from "./routes/DocumentReviewer";
import { DocumentsList } from "./routes/DocumentsList";
import { Settings } from "./routes/Settings";

// Coquille pixel-coherente avec le preview.html : 5 onglets (Tableau de bord /
// Documents / Architecture / Donnees / Parametres). Normes + Regles vivent
// DANS Parametres (cartes), le reviewer est embarque dans le detail Documents
// (la sidebar reste visible) — parite 1:1 avec preview.html.
const navItems: ReadonlyArray<{ to: string; labelKey: string; end?: boolean }> = [
  { to: "/", labelKey: "nav.dashboard", end: true },
  { to: "/documents", labelKey: "nav.documents" },
  { to: "/architecture", labelKey: "nav.architecture" },
  { to: "/data", labelKey: "nav.data" },
  { to: "/settings", labelKey: "nav.settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t } = useTranslation();
  const location = useLocation();
  const currentLang = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  // Le reviewer (detail d'un document) occupe tout le viewport pour maximiser
  // la lisibilite du PDF et des surlignages (disposition split plein ecran) —
  // sidebar masquee. Deviation assumee vs le detail empile du preview.
  const isReviewer = location.pathname.startsWith("/documents/");
  if (isReviewer) {
    return (
      <div className="pr">
        <ErrorBoundary>
          <Routes>
            <Route path="/documents/:id" element={<DocumentReviewer />} />
          </Routes>
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className="pr">
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="brand">{t("app.title")}</span>
            <span className="label">{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          <LlmBadge />

          <nav>
            {navItems.map(({ to, labelKey, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
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
                onClick={() => void i18n.changeLanguage(lng)}
              >
                {lng.toUpperCase()}
              </button>
            ))}
          </div>
        </aside>

        <main>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/documents" element={<DocumentsList />} />
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
