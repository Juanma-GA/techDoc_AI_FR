import { lazy, Suspense, useEffect, useState } from "react";
import {
  Combine,
  Crop,
  Download,
  Eraser,
  FilePenLine,
  FilePlus2,
  Grip,
  Image,
  ImagePlus,
  LockKeyhole,
  MessageSquareText,
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
import { CleanTool } from "./features/clean/CleanTool";
import { CommentsTool } from "./features/comments/CommentsTool";
import { AppShell } from "@internal/techdoc-brand";

import { CropTool } from "./features/crop/CropTool";
import {
  DemoModeBadge,
  DemoModeProvider,
  LanguageSwitcher,
  SidebarNavContent,
  Spinner,
  sidebarNavItemClass,
  type DemoMode,
} from "@internal/ui";
import { DeleteTool } from "./features/delete/DeleteTool";
import { ExtractTool } from "./features/extract/ExtractTool";
import { ExtractImagesTool } from "./features/extract-images/ExtractImagesTool";
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

const MetadataTool = lazy(() =>
  import("./features/metadata/MetadataTool").then((module) => ({ default: module.MetadataTool })),
);

const toolGroups = [
  {
    id: "pages",
    labelKey: "nav.categories.pages",
    tools: [
      { id: "merge", icon: Combine },
      { id: "split", icon: Split },
      { id: "extract", icon: Scissors },
      { id: "insert", icon: FilePlus2 },
      { id: "delete", icon: Trash2 },
      { id: "reorder", icon: Grip },
    ],
  },
  {
    id: "modify",
    labelKey: "nav.categories.modify",
    tools: [
      { id: "crop", icon: Crop },
      { id: "rotate", icon: RotateCw },
      { id: "compress", icon: Minimize2 },
      { id: "clean", icon: Eraser },
      { id: "metadata", icon: FilePenLine },
    ],
  },
  {
    id: "convert",
    labelKey: "nav.categories.convert",
    tools: [
      { id: "extractImages", icon: Download },
      { id: "imagesToPdf", icon: ImagePlus },
      { id: "pdfToImages", icon: Image },
    ],
  },
  {
    id: "annotate",
    labelKey: "nav.categories.annotate",
    tools: [
      { id: "comments", icon: MessageSquareText },
      { id: "signature", icon: PenTool },
    ],
  },
] as const;

const securityTool = { id: "protect", icon: LockKeyhole } as const;
const settingsTool = { id: "settings", icon: SettingsIcon } as const;

type Tool =
  | (typeof toolGroups)[number]["tools"][number]
  | typeof securityTool
  | typeof settingsTool;
type ToolId = Tool["id"];
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
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  const renderToolButton = (tool: Tool) => {
    const Icon = tool.icon;
    return (
      <button
        key={tool.id}
        id={`tool-nav-${tool.id}`}
        type="button"
        aria-current={activeTool === tool.id ? "page" : undefined}
        title={t(`tools.${tool.id}.tab`)}
        className={`${sidebarNavItemClass(activeTool === tool.id)}${tool.id === "settings" ? " pdf-nav-settings" : ""}`}
        onClick={() => setActiveTool(tool.id)}
      >
        <SidebarNavContent icon={Icon} label={t(`tools.${tool.id}.tab`)} />
      </button>
    );
  };

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
            <>
              {toolGroups.map((group, index) => (
                <div className="ui-nav-group" key={group.id}>
                  <div
                    className={`ui-nav-group-title pdf-nav-section-title${index === 0 ? " is-first" : ""}`}
                  >
                    {t(group.labelKey)}
                  </div>
                  <div className="pdf-nav-group-items">
                    {group.tools.map(renderToolButton)}
                  </div>
                </div>
              ))}
              <div className="ui-nav-group">
                <div className="ui-nav-group-title pdf-nav-section-title">
                  {t("nav.categories.security")}
                </div>
                {renderToolButton(securityTool)}
              </div>
              {renderToolButton(settingsTool)}
            </>
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
              <h1 id="tool-panel-title">{t(`tools.${activeTool}.title`)}</h1>
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
              role="region"
              aria-labelledby="tool-panel-title"
              tabIndex={0}
            >
              {activeTool === "merge" ? <MergeTool /> : null}
              {activeTool === "extract" ? <ExtractTool /> : null}
              {activeTool === "extractImages" ? <ExtractImagesTool /> : null}
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
              {activeTool === "clean" ? <CleanTool /> : null}
              {activeTool === "metadata" ? (
                <Suspense fallback={<Spinner aria-label={t("common.loading")} />}>
                  <MetadataTool />
                </Suspense>
              ) : null}
              {activeTool === "protect" ? <ProtectTool /> : null}
              {activeTool === "rotate" ? <RotateTool /> : null}
              {activeTool === "crop" ? <CropTool /> : null}
              {activeTool === "comments" ? <CommentsTool /> : null}
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
