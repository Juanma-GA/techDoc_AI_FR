import { lazy, Suspense, useEffect, useState, type KeyboardEvent } from "react";
import {
  Combine,
  FilePlus2,
  Grip,
  Image,
  ImagePlus,
  LockKeyhole,
  Minimize2,
  PenTool,
  RotateCw,
  Scissors,
  Settings as SettingsIcon,
  ShieldCheck,
  Split,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { CompressTool } from "./features/compress/CompressTool";
import {
  AppShell,
  DemoModeBadge,
  DemoModeProvider,
  LanguageSwitcher,
  SidebarNavContent,
  Spinner,
  sidebarNavItemClass,
  useMediaQuery,
  type DemoMode,
} from "@internal/ui";
import { DeleteTool } from "./features/delete/DeleteTool";
import { ExtractTool } from "./features/extract/ExtractTool";
import { MergeTool } from "./features/merge/MergeTool";
import { ImagesToPdfTool } from "./features/images-to-pdf/ImagesToPdfTool";
import { InsertTool } from "./features/insert/InsertTool";
import { PdfToImagesTool } from "./features/pdf-to-images/PdfToImagesTool";
import { ProtectTool } from "./features/protect/ProtectTool";
import { RotateTool } from "./features/rotate/RotateTool";
import { SignatureTool } from "./features/signature/SignatureTool";
import { SettingsTool } from "./features/settings/SettingsTool";
import { SplitTool } from "./features/split/SplitTool";
import { DemoPdfFileProvider, loadDemoPdf } from "./shared/demoPdf";

const ReorderTool = lazy(() =>
  import("./features/reorder/ReorderTool").then((module) => ({ default: module.ReorderTool })),
);

const tools = [
  { id: "merge", icon: Combine },
  { id: "extract", icon: Scissors },
  { id: "split", icon: Split },
  { id: "insert", icon: FilePlus2 },
  { id: "delete", icon: Trash2 },
  { id: "reorder", icon: Grip },
  { id: "compress", icon: Minimize2 },
  { id: "protect", icon: LockKeyhole },
  { id: "rotate", icon: RotateCw },
  { id: "signature", icon: PenTool },
  { id: "imagesToPdf", icon: ImagePlus },
  { id: "pdfToImages", icon: Image },
  { id: "settings", icon: SettingsIcon },
] as const;

type ToolId = (typeof tools)[number]["id"];
const languages = ["fr", "en"] as const;

declare global {
  interface Window {
    __TAURI__?: {
      window?: {
        getCurrentWindow?: () => {
          setTheme: (theme: "dark" | "light") => Promise<void>;
        };
      };
    };
  }
}

export function App() {
  const { t, i18n } = useTranslation();
  const [activeTool, setActiveTool] = useState<ToolId>("merge");
  const [demoMode, setDemoMode] = useState<DemoMode>("normal");
  const [demoPdfFile, setDemoPdfFile] = useState<File | null>(null);
  const [demoPdfLoading, setDemoPdfLoading] = useState(false);
  const [demoPdfError, setDemoPdfError] = useState(false);
  const isCompact = useMediaQuery("(max-width: 760px)");
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  useEffect(() => {
    const tauri = window.__TAURI__;
    if (!tauri) {
      if ("__TAURI_INTERNALS__" in window) {
        console.error("Tauri window API is unavailable; check withGlobalTauri.");
      }
      return;
    }

    const nativeWindow = tauri.window?.getCurrentWindow?.();
    if (!nativeWindow) {
      console.error("Tauri window API is unavailable; check withGlobalTauri.");
      return;
    }

    const syncTheme = () => {
      const theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
      void nativeWindow.setTheme(theme).catch((error: unknown) => {
        console.error("Unable to synchronize desktop window theme:", error);
      });
    };
    const observer = new MutationObserver(syncTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    syncTheme();

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    document.documentElement.lang = currentLanguage;
    document.title = t("app.documentTitle");
    document
      .querySelector<HTMLMetaElement>('meta[name="description"]')
      ?.setAttribute("content", t("app.metaDescription"));
  }, [currentLanguage, t]);

  const handleDemoModeChange = (mode: DemoMode) => {
    setDemoPdfError(false);
    if (mode === "normal") {
      setDemoMode("normal");
      setDemoPdfFile(null);
      return;
    }
    if (demoPdfLoading || (demoMode === "demo" && demoPdfFile)) {
      return;
    }

    setDemoPdfLoading(true);
    void loadDemoPdf()
      .then((file) => {
        setDemoPdfFile(file);
        setDemoMode("demo");
      })
      .catch((reason: unknown) => {
        console.error("Could not load the demo PDF:", reason);
        setDemoPdfError(true);
      })
      .finally(() => setDemoPdfLoading(false));
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, tool: ToolId) => {
    const currentIndex = tools.findIndex((item) => item.id === tool);
    let nextIndex = currentIndex;

    if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tools.length - 1;
    } else if (event.key === (isCompact ? "ArrowRight" : "ArrowDown")) {
      nextIndex = (currentIndex + 1) % tools.length;
    } else if (event.key === (isCompact ? "ArrowLeft" : "ArrowUp")) {
      nextIndex = (currentIndex - 1 + tools.length) % tools.length;
    } else {
      return;
    }

    event.preventDefault();
    const nextTool = tools[nextIndex]?.id;
    if (!nextTool) throw new RangeError("Invalid tool navigation index");
    setActiveTool(nextTool);
    document.getElementById(`tool-tab-${nextTool}`)?.focus();
  };

  return (
    <DemoModeProvider mode={demoMode} isReady>
      <DemoPdfFileProvider file={demoPdfFile}>
        <AppShell
          className="pdf-toolkit-shell"
          title={t("app.title")}
          brandTitle={t("app.description")}
          navigationLabel={t("nav.ariaLabel")}
          themeToggleLabel={t("nav.themeToggle")}
          collapseLabel={t("nav.collapse")}
          expandLabel={t("nav.expand")}
          sidebarTop={
            demoMode === "demo" ? (
              <div className="border-b border-md px-4 py-2">
                <DemoModeBadge label={t("settings.demo.badge")} />
              </div>
            ) : null
          }
          navigation={
            <div
              className="ui-tool-tabs"
              role="tablist"
              aria-label={t("nav.tools")}
              aria-orientation={isCompact ? "horizontal" : "vertical"}
            >
              {tools.map(({ id, icon: Icon }) => (
                <button
                  key={id}
                  id={`tool-tab-${id}`}
                  type="button"
                  role="tab"
                  aria-controls="tool-panel"
                  aria-selected={activeTool === id}
                  tabIndex={activeTool === id ? 0 : -1}
                  aria-label={t(`tools.${id}.tab`)}
                  title={t(`tools.${id}.tab`)}
                  className={sidebarNavItemClass(activeTool === id)}
                  onClick={() => setActiveTool(id)}
                  onKeyDown={(event) => handleTabKeyDown(event, id)}
                >
                  <SidebarNavContent icon={Icon} label={t(`tools.${id}.tab`)} />
                </button>
              ))}
            </div>
          }
          languageSwitcher={
            <LanguageSwitcher
              languages={languages}
              currentLanguage={currentLanguage}
              onLanguageChange={(language) => void i18n.changeLanguage(language)}
              ariaLabel={t("nav.languageSwitcher")}
            />
          }
        >
          <div className="pdf-workspace">
            <header className="page-header">
              <h1>{t(`tools.${activeTool}.title`)}</h1>
              <p>{t(`tools.${activeTool}.description`)}</p>
              <div className="page-header-actions">
                <div className="local-badge">
                  <ShieldCheck size={15} aria-hidden="true" />
                  <span>{t("app.local")}</span>
                </div>
              </div>
            </header>

            <section
              id="tool-panel"
              className="tool-panel"
              role="tabpanel"
              aria-labelledby={`tool-tab-${activeTool}`}
              tabIndex={0}
            >
              {activeTool === "merge" ? <MergeTool /> : null}
              {activeTool === "extract" ? <ExtractTool /> : null}
              {activeTool === "split" ? <SplitTool /> : null}
              {activeTool === "insert" ? <InsertTool /> : null}
              {activeTool === "delete" ? <DeleteTool /> : null}
              {activeTool === "reorder" ? (
                <Suspense
                  fallback={
                    <p className="preview-status" role="status">
                      <Spinner aria-label={t("common.loading")} />
                      {t("common.loading")}
                    </p>
                  }
                >
                  <ReorderTool />
                </Suspense>
              ) : null}
              {activeTool === "compress" ? <CompressTool /> : null}
              {activeTool === "protect" ? <ProtectTool /> : null}
              {activeTool === "rotate" ? <RotateTool /> : null}
              {activeTool === "signature" ? <SignatureTool /> : null}
              {activeTool === "imagesToPdf" ? <ImagesToPdfTool /> : null}
              {activeTool === "pdfToImages" ? <PdfToImagesTool /> : null}
              {activeTool === "settings" ? (
                <SettingsTool
                  pending={demoPdfLoading}
                  loadError={demoPdfError}
                  onModeChange={handleDemoModeChange}
                />
              ) : null}
            </section>
          </div>
          <footer className="privacy-note">
            <span className="privacy-dot" aria-hidden="true" />
            {t("app.privacy")}
          </footer>
        </AppShell>
      </DemoPdfFileProvider>
    </DemoModeProvider>
  );
}
