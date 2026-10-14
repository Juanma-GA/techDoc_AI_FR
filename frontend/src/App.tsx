import { lazy, Suspense, useState } from "react";
import { ArrowLeft, FileStack, ShieldCheck } from "lucide-react";

import { DeleteTool } from "./features/delete/DeleteTool";
import { ExtractTool } from "./features/extract/ExtractTool";
import { MergeTool } from "./features/merge/MergeTool";
import { HomePage, type ToolId } from "./pages/HomePage";
import { Button } from "./shared/components/Button";

const ReorderTool = lazy(() =>
  import("./features/reorder/ReorderTool").then((module) => ({ default: module.ReorderTool })),
);

const toolTitles: Record<ToolId, string> = {
  merge: "Fusionner des PDF",
  extract: "Extraire des pages",
  delete: "Supprimer des pages",
  reorder: "Réorganiser les pages",
};

export function App() {
  const [activeTool, setActiveTool] = useState<ToolId | null>(null);

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="PDF Toolkit, accueil">
          <span className="brand-mark">
            <FileStack size={22} strokeWidth={2.2} aria-hidden="true" />
          </span>
          <span className="brand-copy">
            <span className="brand-caption">OUTILS DOCUMENTAIRES</span>
            <span className="brand-name">PDF Toolkit</span>
          </span>
        </a>
        <div className="local-badge">
          <ShieldCheck size={16} aria-hidden="true" />
          <span>Traitement local</span>
        </div>
      </header>

      <main className="app-main">
        {activeTool === null ? (
          <HomePage onSelectTool={setActiveTool} />
        ) : (
          <section className="tool-page">
            <Button
              variant="back"
              onClick={() => setActiveTool(null)}
              aria-label="Retour à tous les outils"
            >
              <ArrowLeft size={17} aria-hidden="true" />
              Tous les outils
            </Button>
            <div className="tool-page-heading">
              <p className="eyebrow">PDF TOOLKIT</p>
              <h1>{toolTitles[activeTool]}</h1>
              <p>Choisissez un fichier PDF pour démarrer le traitement sur cette machine.</p>
            </div>
            {activeTool === "merge" ? <MergeTool /> : null}
            {activeTool === "extract" ? <ExtractTool /> : null}
            {activeTool === "delete" ? <DeleteTool /> : null}
            {activeTool === "reorder" ? (
              <Suspense
                fallback={
                  <p className="preview-status" role="status">
                    <span className="spinner" aria-hidden="true" />
                    Chargement de l'outil de réorganisation…
                  </p>
                }
              >
                <ReorderTool />
              </Suspense>
            ) : null}
          </section>
        )}
      </main>

      <footer className="app-footer">
        <span>PDF Toolkit</span>
        <span>Pas de compte · Pas de base de données · Temporaires supprimés après traitement</span>
      </footer>
    </div>
  );
}
