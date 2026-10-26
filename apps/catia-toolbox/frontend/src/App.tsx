import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  SidebarNavContent,
  sidebarNavItemClass,
  type SidebarNavIconName,
} from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { LlmBadge } from "./components/LlmBadge";
import i18n from "./i18n";
import { healthApi, importsApi, identificationApi } from "./lib/api";
import { Checks } from "./routes/Checks";
import { Colorization } from "./routes/Colorization";
import { Conversion } from "./routes/Conversion";
import { Data } from "./routes/Data";
import { Diff } from "./routes/Diff";
import { Identification } from "./routes/Identification";
import { Qc } from "./routes/Qc";
import { Replacement } from "./routes/Replacement";
import { Settings } from "./routes/Settings";
import { SmgxmlRename } from "./routes/SmgxmlRename";
import { TreeOptimization } from "./routes/TreeOptimization";
import { useWorkspace } from "./stores/workspace";

type NavLeaf = { to: string; labelKey: string; icon: SidebarNavIconName; end?: boolean };
type NavGroup = { groupKey: string; items: NavLeaf[] };
type NavEntry = NavLeaf | NavGroup;

const isGroup = (e: NavEntry): e is NavGroup => "groupKey" in e;

/** Navigation groupee, ordre et libelles fideles au preview (lignes 176-206). */
const NAV: NavEntry[] = [
  {
    groupKey: "nav.groups.identification",
    items: [
      { to: "/identification", labelKey: "nav.identification", icon: "file" },
      { to: "/diff", labelKey: "nav.diff", icon: "compare" },
    ],
  },
  {
    groupKey: "nav.groups.preparation",
    items: [{ to: "/conversion", labelKey: "nav.conversion", icon: "convert" }],
  },
  {
    groupKey: "nav.groups.traitement",
    items: [
      { to: "/tree", labelKey: "nav.optimizationTree", icon: "tree" },
      { to: "/colorization", labelKey: "nav.colorization", icon: "color" },
    ],
  },
  {
    groupKey: "nav.groups.integration",
    items: [
      { to: "/smgxml-rename", labelKey: "nav.smgxmlRename", icon: "rename" },
      { to: "/replacement", labelKey: "nav.replacement", icon: "replacement" },
    ],
  },
  {
    groupKey: "nav.groups.controle",
    items: [
      { to: "/qc", labelKey: "nav.qc", icon: "quality" },
      { to: "/checks", labelKey: "nav.checks", icon: "rules" },
    ],
  },
  {
    groupKey: "nav.groups.outils",
    items: [{ to: "/settings", labelKey: "nav.settings", icon: "settings" }],
  },
];

/** Titre + sous-titre par route (entete centralise du main). */
export const ROUTE_META: Record<string, { titleKey: string; subKey: string }> = {
  "/identification": { titleKey: "page.identification.title", subKey: "page.identification.sub" },
  "/diff": { titleKey: "page.diff.title", subKey: "page.diff.sub" },
  "/conversion": { titleKey: "page.conversion.title", subKey: "page.conversion.sub" },
  "/colorization": { titleKey: "page.colorization.title", subKey: "page.colorization.sub" },
  "/tree": { titleKey: "page.optimizationTree.title", subKey: "page.optimizationTree.sub" },
  "/smgxml-rename": { titleKey: "page.smgxmlRename.title", subKey: "page.smgxmlRename.sub" },
  "/replacement": { titleKey: "page.replacement.title", subKey: "page.replacement.sub" },
  "/qc": { titleKey: "page.qc.title", subKey: "page.qc.sub" },
  "/checks": { titleKey: "page.checks.title", subKey: "page.checks.sub" },
  "/settings": { titleKey: "page.settings.title", subKey: "page.settings.sub" },
};

const navItemClass = ({ isActive }: { isActive: boolean }) =>
  sidebarNavItemClass(isActive);

function WorkspaceBootstrap() {
  const importId = useWorkspace((state) => state.importId);
  const nomenclatureRunId = useWorkspace((state) => state.nomenclatureRunId);
  const setImport = useWorkspace((state) => state.setImport);
  const setNomenclatureRun = useWorkspace((state) => state.setNomenclatureRun);
  const validated = useRef(false);

  const healthQuery = useQuery({ queryKey: ["health"], queryFn: healthApi.get });
  const importsQuery = useQuery({
    queryKey: ["imports"],
    queryFn: importsApi.list,
    enabled: healthQuery.isSuccess,
  });
  const nomenclaturesQuery = useQuery({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
    enabled: healthQuery.isSuccess,
  });
  useEffect(() => {
    if (
      validated.current ||
      !healthQuery.isSuccess ||
      !importsQuery.isSuccess ||
      !nomenclaturesQuery.isSuccess
    ) return;

    if (importId && !importsQuery.data.some((item) => item.id === importId)) {
      setImport(null);
    }
    if (nomenclatureRunId && !nomenclaturesQuery.data.some((run) => run.id === nomenclatureRunId)) {
      setNomenclatureRun(null);
    }
    validated.current = true;
  }, [
    importId,
    healthQuery.isSuccess,
    importsQuery.data,
    importsQuery.isSuccess,
    nomenclatureRunId,
    nomenclaturesQuery.data,
    nomenclaturesQuery.isSuccess,
    setImport,
    setNomenclatureRun,
  ]);

  return null;
}

export function App() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const meta = ROUTE_META[pathname] ?? ROUTE_META["/identification"]!;
  const lang = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  return (
    <AppShell
      className="ct"
      title={t("app.title")}
      brandTitle={t("app.description")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      llmStatus={<LlmBadge />}
      navigation={NAV.map((entry) =>
        isGroup(entry) ? (
          <div key={entry.groupKey} className="ui-nav-group">
            <div className="ui-nav-group-title">{t(entry.groupKey)}</div>
            {entry.items.map(({ to, labelKey, icon }) => {
              const label = t(labelKey);
              return (
                <NavLink
                  key={to}
                  to={to}
                  title={label}
                  aria-label={label}
                  className={navItemClass}
                >
                  <SidebarNavContent icon={icon} label={label} />
                </NavLink>
              );
            })}
          </div>
        ) : (
          <NavLink
            key={entry.to}
            to={entry.to}
            end={entry.end}
            title={t(entry.labelKey)}
            aria-label={t(entry.labelKey)}
            className={navItemClass}
          >
            <SidebarNavContent icon={entry.icon} label={t(entry.labelKey)} />
          </NavLink>
        ),
      )}
      languageSwitcher={
        <LanguageSwitcher
          languages={["fr", "en"]}
          currentLanguage={lang}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
        />
      }
    >
      <WorkspaceBootstrap />
      <div className="page-header">
        <h1>{t(meta.titleKey)}</h1>
        {meta.subKey ? <p>{t(meta.subKey)}</p> : null}
      </div>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<Navigate to="/identification" replace />} />
          <Route path="/identification" element={<Identification />} />
          <Route path="/diff" element={<Diff />} />
          <Route path="/conversion" element={<Conversion />} />
          <Route path="/colorization" element={<Colorization />} />
          <Route path="/tree" element={<TreeOptimization />} />
          <Route path="/smgxml-recolor" element={<Navigate to="/colorization" replace />} />
          <Route path="/suggestions" element={<Navigate to="/tree" replace />} />
          <Route path="/export" element={<Navigate to="/identification" replace />} />
          <Route path="/smgxml-rename" element={<SmgxmlRename />} />
          <Route path="/replacement" element={<Replacement />} />
          <Route path="/qc" element={<Qc />} />
          <Route path="/checks" element={<Checks />} />
          <Route path="/data" element={<Data />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}
