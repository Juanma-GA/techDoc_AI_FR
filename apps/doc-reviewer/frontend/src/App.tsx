import { Button } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
import i18n from "./i18n";
import { Dashboard } from "./routes/Dashboard";
import { Data } from "./routes/Data";
import { DocumentReviewer } from "./routes/DocumentReviewer";
import { DocumentsList } from "./routes/DocumentsList";
import { Settings } from "./routes/Settings";

// Navigation items: Tableau de bord / Documents / Donnees / Parametres.
// Layout construit avec Tailwind + @internal/ui (plus de preview-skin.css).
const navItems: ReadonlyArray<{ to: string; labelKey: string; end?: boolean }> = [
  { to: "/", labelKey: "nav.dashboard", end: true },
  { to: "/documents", labelKey: "nav.documents" },
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
  // sidebar masquee.
  const isReviewer = location.pathname.startsWith("/documents/");
  if (isReviewer) {
    return (
      <div className="h-full min-h-screen bg text-fg">
        <ErrorBoundary>
          <Routes>
            <Route path="/documents/:id" element={<DocumentReviewer />} />
          </Routes>
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className="h-full min-h-screen bg text-fg">
      <div className="flex h-screen">
        {/* Sidebar */}
        <aside className="w-64 flex-shrink-0 border-r border bg-2 flex flex-col">
          {/* Header */}
          <div className="flex items-baseline gap-2 p-4 border-b border-base">
            <span className="font-display text-lg text-brand-blue-light">{t("app.title")}</span>
            <span className="font-mono uppercase text-xs tracking-widest text-fg-muted">{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          {/* LLM Badge */}
          <LlmBadge />

          {/* Navigation */}
          <nav className="flex-1 flex flex-col gap-1 p-3 overflow-y-auto">
            {navItems.map(({ to, labelKey, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  isActive
                    ? "flex items-center px-3 py-2 rounded-lg bg-brand text-fg text-sm font-medium transition-colors"
                    : "flex items-center px-3 py-2 rounded-lg text-fg-dim hover:bg-card-hover hover:text-fg text-sm font-medium transition-colors cursor-pointer"
                }
              >
                {t(labelKey)}
              </NavLink>
            ))}
          </nav>

          {/* Language Switcher */}
          <div className="flex gap-1 p-3 border-t border-base">
            {LANGS.map((lng) => (
              <Button
                key={lng}
                variant={currentLang === lng ? "default" : "outline"}
                size="sm"
                onClick={() => void i18n.changeLanguage(lng)}
                className="flex-1 text-xs"
              >
                {lng.toUpperCase()}
              </Button>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto px-8 py-6">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/documents" element={<DocumentsList />} />
              <Route path="/data" element={<Data />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
