import { lazy, Suspense, useEffect, useState, type KeyboardEvent } from "react";
import {
  Combine,
  Grip,
  Image,
  ImagePlus,
  Minimize2,
  RotateCw,
  Scissors,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { CompressTool } from "./features/compress/CompressTool";
import { AppShell, sidebarNavItemClass } from "./shared/components/AppShell";
import { LanguageSwitcher } from "./shared/components/LanguageSwitcher";
import { useMediaQuery } from "./shared/hooks/useMediaQuery";
import { DeleteTool } from "./features/delete/DeleteTool";
import { ExtractTool } from "./features/extract/ExtractTool";
import { MergeTool } from "./features/merge/MergeTool";
import { ImagesToPdfTool } from "./features/images-to-pdf/ImagesToPdfTool";
import { PdfToImagesTool } from "./features/pdf-to-images/PdfToImagesTool";
import { RotateTool } from "./features/rotate/RotateTool";

const ReorderTool = lazy(() =>
  import("./features/reorder/ReorderTool").then((module) => ({ default: module.ReorderTool })),
);

const tools = [
  { id: "merge", icon: Combine },
  { id: "extract", icon: Scissors },
  { id: "delete", icon: Trash2 },
  { id: "reorder", icon: Grip },
  { id: "compress", icon: Minimize2 },
  { id: "rotate", icon: RotateCw },
  { id: "imagesToPdf", icon: ImagePlus },
  { id: "pdfToImages", icon: Image },
] as const;

type ToolId = (typeof tools)[number]["id"];
const languages = ["fr", "en"] as const;

export function App() {
  const { t, i18n } = useTranslation();
  const [activeTool, setActiveTool] = useState<ToolId>("merge");
  const isCompact = useMediaQuery("(max-width: 760px)");
  const currentLanguage = (i18n.resolvedLanguage ?? i18n.language ?? "fr").slice(0, 2);

  useEffect(() => {
    document.documentElement.lang = currentLanguage;
    document.title = t("app.documentTitle");
    document
      .querySelector<HTMLMetaElement>('meta[name="description"]')
      ?.setAttribute("content", t("app.metaDescription"));
  }, [currentLanguage, t]);

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
    const nextTool = tools[nextIndex].id;
    setActiveTool(nextTool);
    document.getElementById(`tool-tab-${nextTool}`)?.focus();
  };

  return (
    <AppShell
      title={t("app.title")}
      brandTitle={t("app.description")}
      version={t("app.version")}
      navigationLabel={t("nav.ariaLabel")}
      themeToggleLabel={t("nav.themeToggle")}
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
              className={sidebarNavItemClass(activeTool === id)}
              onClick={() => setActiveTool(id)}
              onKeyDown={(event) => handleTabKeyDown(event, id)}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{t(`tools.${id}.tab`)}</span>
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
          {activeTool === "delete" ? <DeleteTool /> : null}
          {activeTool === "compress" ? <CompressTool /> : null}
          {activeTool === "rotate" ? <RotateTool /> : null}
          {activeTool === "imagesToPdf" ? <ImagesToPdfTool /> : null}
          {activeTool === "pdfToImages" ? <PdfToImagesTool /> : null}
          {activeTool === "reorder" ? (
            <Suspense
              fallback={
                <p className="preview-status" role="status">
                  <span className="spinner" aria-hidden="true" />
                  {t("common.loading")}
                </p>
              }
            >
              <ReorderTool />
            </Suspense>
          ) : null}
        </section>
      </div>
      <footer className="privacy-note">
        <span className="privacy-dot" aria-hidden="true" />
        {t("app.privacy")}
      </footer>
    </AppShell>
  );
}
