import { useQuery } from "@tanstack/react-query";
import {
  Ai4TechDocLogo,
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  ErrorBoundary,
  LanguageSwitcher,
  LlmStatus,
  sidebarNavItemClass,
} from "@internal/ui";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { healthApi, settingsApi, type HealthDto, type SettingsDto } from "./lib/api";
import { Data } from "./routes/Data";
import { Home } from "./routes/Home";
import { Settings } from "./routes/Settings";

const LANGUAGES = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const healthQuery = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });
  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });
  const demoEnabled = settingsQuery.data?.demo_enabled ?? false;

  return (
    <AppShell
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      headerStart={<Ai4TechDocLogo alt="" />}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      sidebarTop={
        demoEnabled ? (
          <div className="border-b border-md px-4 py-2">
            <DemoModeBadge label={t("demo.badge")} />
          </div>
        ) : null
      }
      navigation={
        <>
          <NavLink to="/" end className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.home")}
          </NavLink>
          <NavLink to="/data" className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.data")}
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => sidebarNavItemClass(isActive)}>
            {t("nav.settings")}
          </NavLink>
        </>
      }
      llmStatus={
        <LlmStatus
          status={healthQuery.data?.llm}
          labels={{
            label: t("llm.label"),
            title: t("llm.title"),
            on: t("llm.on"),
            off: t("llm.off"),
            untested: t("llm.untested"),
            noKey: t("llm.noKey"),
          }}
        />
      }
      languageSwitcher={
        <LanguageSwitcher
          languages={LANGUAGES}
          currentLanguage={currentLanguage}
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
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/data" element={<Data />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </ErrorBoundary>
      </DemoModeProvider>
    </AppShell>
  );
}
