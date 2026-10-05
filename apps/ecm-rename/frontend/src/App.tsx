import { useQuery } from "@tanstack/react-query";
import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  LlmStatus,
  sidebarNavItemClass,
} from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";

import { healthApi, type HealthDto, type ProcessDto } from "./lib/api";
import { Data } from "./routes/Data";
import { Home } from "./routes/Home";
import { Settings } from "./routes/Settings";

const LANGUAGES = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);
  const [lastResult, setLastResult] = useState<ProcessDto | null>(null);
  const healthQuery = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
    refetchInterval: 15_000,
  });

  return (
    <AppShell
      className="ecm"
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      navigationLabel={t("app.navigation")}
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
          ariaLabel={t("app.language")}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
        />
      }
    >
      <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Home onProcessed={setLastResult} />} />
            <Route path="/data" element={<Data result={lastResult} />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}
