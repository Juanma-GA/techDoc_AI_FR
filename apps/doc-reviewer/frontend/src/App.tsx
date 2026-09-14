import { ErrorBoundary } from "@internal/ui";
import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import i18n from "./i18n";

const Dashboard = lazy(async () => ({
  default: (await import("./routes/Dashboard")).Dashboard,
}));
const DocumentReviewer = lazy(async () => ({
  default: (await import("./routes/DocumentReviewer")).DocumentReviewer,
}));
const DocumentsList = lazy(async () => ({
  default: (await import("./routes/DocumentsList")).DocumentsList,
}));
const Settings = lazy(async () => ({
  default: (await import("./routes/Settings")).Settings,
}));

function RouteFallback() {
  return (
    <div className="empty-state" aria-busy="true">
      <span className="spinner" />
    </div>
  );
}

// Coquille pixel-coherente avec le preview.html : 4 onglets (Tableau de bord /
// Documents / Parametres). Normes + Regles vivent
// DANS Parametres (cartes), le reviewer est embarque dans le detail Documents
// (la sidebar reste visible) — parite 1:1 avec preview.html.
const navItems: ReadonlyArray<{ to: string; labelKey: string; end?: boolean }> = [
  { to: "/", labelKey: "nav.dashboard", end: true },
  { to: "/documents", labelKey: "nav.documents" },
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
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/documents/:id" element={<DocumentReviewer />} />
            </Routes>
          </Suspense>
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
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/documents" element={<DocumentsList />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
