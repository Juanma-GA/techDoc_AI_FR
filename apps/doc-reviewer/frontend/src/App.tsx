import {
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  ErrorBoundary,
  LanguageSwitcher,
  SidebarNavContent,
  sidebarNavItemClass,
} from "@internal/ui";
import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { useMistralSettings } from "./hooks/useMistralSettings";
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
const DocumentComparison = lazy(async () => ({
  default: (await import("./routes/DocumentComparison")).DocumentComparison,
}));
const Preparation = lazy(async () => ({
  default: (await import("./routes/Preparation")).Preparation,
}));
const PreparationWorkspace = lazy(async () => ({
  default: (await import("./routes/PreparationWorkspace")).PreparationWorkspace,
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
const navItems: ReadonlyArray<{
  to: string;
  labelKey: string;
  icon: "home" | "files" | "workflow" | "review" | "rules" | "settings";
  end?: boolean;
}> = [
  { to: "/", labelKey: "nav.dashboard", icon: "home", end: true },
  { to: "/preparation", labelKey: "nav.preparation", icon: "workflow" },
  { to: "/documents", labelKey: "nav.documents", icon: "files" },
  { to: "/rejections", labelKey: "nav.rejections", icon: "review" },
  { to: "/rules", labelKey: "nav.rules", icon: "rules" },
  { to: "/settings", labelKey: "nav.settings", icon: "settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t } = useTranslation();
  const location = useLocation();
  const settingsQuery = useMistralSettings();
  const currentLang = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  // Le reviewer (detail d'un document) occupe tout le viewport pour maximiser
  // la lisibilite du PDF et des surlignages (disposition split plein ecran) —
  // sidebar masquee. Deviation assumee vs le detail empile du preview.
  const isReviewer = location.pathname.startsWith("/documents/");
  if (isReviewer) {
    return (
      <DemoModeProvider
        mode={demoEnabled ? "demo" : "normal"}
        isReady={settingsQuery.isSuccess}
      >
        <div className="pr">
          <ErrorBoundary>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/documents/:id" element={<DocumentReviewer />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </div>
      </DemoModeProvider>
    );
  }

  return (
    <AppShell
      className="pr"
      title={t("app.title")}
      brandTitle={t("app.description")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      sidebarTop={
        demoEnabled ? (
          <div className="border-b border-md px-4 py-2">
            <DemoModeBadge label={t("demo.badge")} />
          </div>
        ) : null
      }
      llmStatus={<LlmBadge />}
      navigation={navItems.map(({ to, labelKey, icon, end }) => {
        const label = t(labelKey);
        return (
          <NavLink
            key={to}
            to={to}
            end={end}
            title={label}
            aria-label={label}
            className={({ isActive }) => sidebarNavItemClass(isActive)}
          >
            <SidebarNavContent icon={icon} label={label} />
          </NavLink>
        );
      })}
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGS}
          currentLanguage={currentLang}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
          ariaLabel={t("nav.languageSwitcher")}
        />
      }
    >
      <DemoModeProvider
        mode={demoEnabled ? "demo" : "normal"}
        isReady={settingsQuery.isSuccess}
      >
        <ErrorBoundary>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/documents" element={<DocumentsList />} />
              <Route path="/comparison" element={<DocumentComparison />} />
              <Route path="/preparation" element={<Preparation />} />
              <Route path="/preparation/:id" element={<PreparationWorkspace />} />
              <Route path="/rejections" element={<Rejections />} />
              <Route path="/rules" element={<Rules />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </DemoModeProvider>
    </AppShell>
  );
}
