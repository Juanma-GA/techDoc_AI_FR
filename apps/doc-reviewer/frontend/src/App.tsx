import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  sidebarNavItemClass,
} from "@internal/ui";
import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
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
const Rules = lazy(async () => ({
  default: (await import("./routes/Rules")).Rules,
}));
const Rejections = lazy(async () => ({
  default: (await import("./routes/Rejections")).Rejections,
}));

function RouteFallback() {
  return (
    <div className="empty-state" aria-busy="true">
      <span className="spinner" />
    </div>
  );
}

// Navigation principale et reviewer plein ecran pour le document courant.
const navItems: ReadonlyArray<{ to: string; labelKey: string; end?: boolean }> = [
  { to: "/", labelKey: "nav.dashboard", end: true },
  { to: "/documents", labelKey: "nav.documents" },
  { to: "/rejections", labelKey: "nav.rejections" },
  { to: "/rules", labelKey: "nav.rules" },
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
    <AppShell
      className="pr"
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      llmStatus={<LlmBadge />}
      navigation={navItems.map(({ to, labelKey, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => sidebarNavItemClass(isActive)}
        >
          {t(labelKey)}
        </NavLink>
      ))}
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGS}
          currentLanguage={currentLang}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
          ariaLabel={t("nav.languageSwitcher")}
        />
      }
    >
      <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<DocumentsList />} />
            <Route path="/rejections" element={<Rejections />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}
