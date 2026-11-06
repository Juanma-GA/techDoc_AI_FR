import { AppShell } from "@internal/techdoc-brand";

import {
  DemoModeBadge,
  DemoModeProvider,
  ErrorBoundary,
  LanguageSwitcher,
  PortalLink,
  SidebarNavContent,
  sidebarNavItemClass,
} from "@internal/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import { authApi, settingsApi, type AuthSessionDto, type SettingsDto } from "./lib/api";
import { Data } from "./routes/Data";
import { Documents } from "./routes/Documents";
import { Generate } from "./routes/Generate";
import { Sessions } from "./routes/Sessions";
import { Settings } from "./routes/Settings";

// Coquille pixel-identique au preview.html : .layout / .sidebar / .nav-item /
// .lang-switch (CSS dans styles/preview-skin.css). Pas de logos sur les onglets.
const navItems = [
  { to: "/", labelKey: "nav.generate", icon: "home" },
  { to: "/documents", labelKey: "nav.documents", icon: "files" },
  { to: "/sessions", labelKey: "nav.sessions", icon: "chat" },
  { to: "/settings", labelKey: "nav.settings", icon: "settings" },
] as const;

const LANGS = ["fr", "en", "es"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language || "fr").slice(0, 2);
  const qc = useQueryClient();

  // MFA pilot (R1) : tant que auth_enabled=false (defaut tier1), `enabled`
  // vaut false et la porte ci-dessous est un no-op — comportement identique
  // a avant ce pilote.
  const sessionQuery = useQuery<AuthSessionDto>({
    queryKey: ["auth", "session"],
    queryFn: authApi.session,
    staleTime: 60_000,
  });
  const session = sessionQuery.data;
  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  const logout = async () => {
    await authApi.logout();
    void qc.invalidateQueries({ queryKey: ["auth", "session"] });
  };

  // Session pas encore chargee (premier rendu) : ne rien afficher plutot
  // qu'un flash de l'app avant de savoir si une connexion est requise.
  if (sessionQuery.isPending) {
    return null;
  }

  // SSO portal (option A) : le login n'est PAS ici, il est au portal
  // atexispocs. Si l'auth est active et qu'aucune session partagee n'est
  // presente, on renvoie au portal (parent de BASE_URL) plutot que
  // d'afficher un formulaire propre. No-op quand auth_enabled=false.
  if (session?.enabled && !session.authenticated) {
    // BASE_URL de doc-writer = ".../atexispocs/doc-writer/" -> le portal est
    // le parent ".../atexispocs/". En local (BASE_URL="/") -> "/".
    const base = import.meta.env.BASE_URL || "/";
    const portalUrl = base.replace(/[^/]+\/$/, "") || "/";
    window.location.replace(portalUrl);
    return null;
  }

  return (
    <AppShell
      className="dw"
      title={t("app.title")}
      brandTitle={t("app.title")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      sidebarTop={
        <>
          <PortalLink className="sidebar-home" label={t("nav.portal")} />
          {demoEnabled ? (
            <div className="px-4 py-2">
              <DemoModeBadge label={t("demo.badge")} />
            </div>
          ) : null}
          {session?.enabled && session.authenticated ? (
            <div className="current-user-badge">
              {session.display_name || session.email}
              {" · "}
              <button type="button" className="btn ghost small" onClick={() => void logout()}>
                {t("auth.logout")}
              </button>
            </div>
          ) : null}
        </>
      }
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
        />
      }
    >
      <DemoModeProvider
        mode={demoEnabled ? "demo" : "normal"}
        isReady={settingsQuery.isSuccess}
      >
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Generate />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </ErrorBoundary>
      </DemoModeProvider>
    </AppShell>
  );
}
