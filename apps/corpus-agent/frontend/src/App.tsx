import { Button, PortalLink } from "@internal/ui";
import { lazy, Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { LlmBadge } from "./components/LlmBadge";
import { ThemeToggleButton } from "./components/ThemeToggleButton";
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

// Navigation items sans logos. Layout construit avec Tailwind + @internal/ui.
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
    <div className="h-full min-h-screen bg-bg text-fg">
      <div className="flex h-screen">
        {/* Sidebar */}
        <aside className="w-64 flex-shrink-0 border-r border-base bg-bg-2 flex flex-col">
          {/* Header */}
          <div className="flex items-baseline gap-2 p-4 border-b border-base">
            <PortalLink className="flex-shrink-0" label={t("nav.portal")} title="Portal" />
            <span className="font-display text-lg text-brand-blue-light" title={t("app.titleTooltip")}>
              {t("app.title")}
            </span>
            <span className="font-mono uppercase text-xs tracking-widest text-fg-muted">{t("app.version")}</span>
            <ThemeToggleButton />
          </div>

          {/* LLM Badge */}
          <LlmBadge />

          {/* Navigation */}
          <nav className="flex-1 flex flex-col gap-1 p-3 overflow-y-auto">
            {navItems.map(({ to, labelKey }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  isActive
                    ? "flex items-center px-3 py-2 rounded-lg bg-brand text-fg text-sm font-medium transition-colors"
                    : "flex items-center px-3 py-2 rounded-lg text-fg-dim hover:bg-card-hover hover:text-fg text-sm font-medium transition-colors cursor-pointer"
                }
                onClick={handleNavClick(to)}
              >
                {t(labelKey)}
              </NavLink>
            ))}
          </nav>

          {/* Unsaved Guard Banner */}
          {pendingTo && (
            <div className="bg-warning/10 border-t border-warning text-warning-600 p-3 space-y-2">
              <p className="text-sm font-medium">{guardMessage}</p>
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  size="sm"
                  onClick={confirmLeave}
                  className="flex-1"
                >
                  {t("nav.leaveWithoutSaving")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingTo(null)}
                  className="flex-1"
                >
                  {t("nav.stayHere")}
                </Button>
              </div>
            </div>
          )}

          {/* Language Switcher */}
          <div className="flex gap-1 p-3 border-t border-base">
            {LANGS.map((lng) => (
              <Button
                key={lng}
                variant={currentLang === lng ? "default" : "outline"}
                size="sm"
                onClick={() => void setAppLanguage(lng)}
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
            <Suspense fallback={<div className="flex items-center justify-center h-screen text-fg-muted">{t("common.loading")}</div>}>
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
