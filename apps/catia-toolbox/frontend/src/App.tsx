import {
  AppShell,
  ErrorBoundary,
  LanguageSwitcher,
  Select,
  Spinner,
  SidebarNavContent,
  sidebarNavItemClass,
  type SidebarNavIconName,
  useMediaQuery,
} from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import i18n from "./i18n";
import { healthApi, importsApi, identificationApi } from "./lib/api";
import { useWorkspace } from "./stores/workspace";

const Identification = lazy(() => import("./routes/Identification").then((module) => ({ default: module.Identification })));
const Diff = lazy(() => import("./routes/Diff").then((module) => ({ default: module.Diff })));
const Conversion = lazy(() => import("./routes/Conversion").then((module) => ({ default: module.Conversion })));
const TreeOptimization = lazy(() => import("./routes/TreeOptimization").then((module) => ({ default: module.TreeOptimization })));
const Colorization = lazy(() => import("./routes/Colorization").then((module) => ({ default: module.Colorization })));
const SmgxmlRename = lazy(() => import("./routes/SmgxmlRename").then((module) => ({ default: module.SmgxmlRename })));
const Data = lazy(() => import("./routes/Data").then((module) => ({ default: module.Data })));
const Settings = lazy(() => import("./routes/Settings").then((module) => ({ default: module.Settings })));

type NavLeaf = { to: string; labelKey: string; icon: SidebarNavIconName; end?: boolean };
type NavGroup = { groupKey: string; items: NavLeaf[] };
type NavEntry = NavLeaf | NavGroup;

const isGroup = (e: NavEntry): e is NavGroup => "groupKey" in e;

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
    ],
  },
  {
    groupKey: "nav.groups.outils",
    items: [
      { to: "/data", labelKey: "nav.data", icon: "data" },
      { to: "/settings", labelKey: "nav.settings", icon: "settings" },
    ],
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
  "/settings": { titleKey: "page.settings.title", subKey: "page.settings.sub" },
  "/data": { titleKey: "nav.data", subKey: "" },
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
  const navigate = useNavigate();
  const compactNavigation = useMediaQuery("(max-width: 760px)");
  const navItems = NAV.flatMap((entry) => isGroup(entry) ? entry.items : [entry]);
  const meta = ROUTE_META[pathname] ?? ROUTE_META["/identification"]!;
  const lang = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  useEffect(() => {
    document.title = t("app.title");
  }, [t]);

  return (
    <AppShell
      className="ct"
      mainClassName="workspace-main"
      title={t("app.title")}
      brandTitle={t("app.description")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
      collapseLabel={t("nav.collapse")}
      expandLabel={t("nav.expand")}
      navigation={compactNavigation ? (
        <Select
          className="min-w-0"
          aria-label={t("nav.ariaLabel")}
          value={navItems.some((item) => item.to === pathname) ? pathname : "/identification"}
          options={navItems.map((item) => ({ value: item.to, label: t(item.labelKey) }))}
          onChange={(event) => navigate(event.target.value)}
        />
      ) : NAV.map((entry) =>
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
          ariaLabel={t("nav.languageSwitcher")}
          onLanguageChange={(language) => void i18n.changeLanguage(language)}
        />
      }
    >
      <WorkspaceBootstrap />
      <header className="page-header">
        <h1 className="break-words">{t(meta.titleKey)}</h1>
        {meta.subKey ? <p>{t(meta.subKey)}</p> : null}
      </header>
      <ErrorBoundary key={pathname}>
        <Suspense fallback={
          <div className="flex min-h-32 items-center justify-center" data-testid="route-loading">
            <Spinner aria-label={t("common.loading")} />
          </div>
        }>
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
          <Route path="/data" element={<Data />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/identification" replace />} />
        </Routes>
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}
