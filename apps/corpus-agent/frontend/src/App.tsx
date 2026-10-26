import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  PortalLink,
  SidebarNavContent,
  sidebarNavItemClass,
} from "@internal/ui";
import { lazy, Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { setAppLanguage } from "./i18n";
import { useUnsavedGuardStore } from "./stores/useUnsavedGuardStore";

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
  { to: "/", labelKey: "nav.manager", icon: "home" },
  { to: "/projects", labelKey: "nav.projects", icon: "project" },
  { to: "/redacteur", labelKey: "nav.redacteur", icon: "file" },
  { to: "/chatbot", labelKey: "nav.chatbot", icon: "chat" },
  { to: "/data", labelKey: "nav.data", icon: "data" },
  { to: "/settings", labelKey: "nav.settings", icon: "settings" },
] as const;

const LANGS = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);
  const navigate = useNavigate();
  const location = useLocation();
  const guardMessage = useUnsavedGuardStore((s) => s.message);
  // Onglet cible en attente de confirmation (clic intercepte pendant qu'une
  // page a des modifications non enregistrees, cf. useUnsavedGuardStore).
  const [pendingTo, setPendingTo] = useState<string | null>(null);

  // Fermeture d'onglet / rechargement / URL tapee a la main : seul le
  // navigateur peut demander confirmation a ce stade (dialogue natif standard
  // de l'evenement `beforeunload`, jamais un popup declenche par notre propre
  // code -> hors perimetre de la regle #2, qui vise nos propres popups).
  useEffect(() => {
    if (!guardMessage) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [guardMessage]);

  // Navigation interne (clic sur un onglet de la sidebar) : interceptee tant
  // qu'une garde est active, avec une confirmation maison (jamais de popup
  // natif, regle #2) affichee sous la sidebar.
  const handleNavClick = (to: string) => (e: React.MouseEvent) => {
    if (guardMessage && to !== location.pathname) {
      e.preventDefault();
      setPendingTo(to);
    }
  };
  const confirmLeave = () => {
    if (!pendingTo) return;
    useUnsavedGuardStore.getState().setGuard(null);
    const to = pendingTo;
    setPendingTo(null);
    navigate(to);
  };

  return (
    <AppShell
      className="ca"
      title={t("app.title")}
      brandTitle={t("app.titleTooltip")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      sidebarTop={<PortalLink className="sidebar-home" label={t("nav.portal")} />}
      llmStatus={<LlmBadge />}
      navigation={navItems.map(({ to, labelKey, icon }) => {
        const label = t(labelKey);
        return (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            title={label}
            aria-label={label}
            className={({ isActive }) => sidebarNavItemClass(isActive)}
            onClick={handleNavClick(to)}
          >
            <SidebarNavContent icon={icon} label={label} />
          </NavLink>
        );
      })}
      sidebarBottom={
        pendingTo ? (
          <div className="banner warn" style={{ margin: "8px 12px" }}>
            {guardMessage}
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <button type="button" className="btn danger small" onClick={confirmLeave}>
                {t("nav.leaveWithoutSaving")}
              </button>
              <button type="button" className="btn ghost small" onClick={() => setPendingTo(null)}>
                {t("nav.stayHere")}
              </button>
            </div>
          </div>
        ) : null
      }
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGS}
          currentLanguage={currentLang}
          onLanguageChange={(language) => {
            if (language === "fr" || language === "en") void setAppLanguage(language);
          }}
        />
      }
    >
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
    </AppShell>
  );
}
