import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { PdfViewer } from "../components/reviewer/PdfViewer";
import { AnalysisTargetBanner } from "../components/reviewer/AnalysisTargetBanner";
import { AnalysisPageRange } from "../components/reviewer/AnalysisPageRange";
import { DocumentMetaPanel } from "../components/reviewer/DocumentMetaPanel";
import { SuggestionPanel } from "../components/reviewer/SuggestionPanel";
import { ExportSelector } from "../components/reviewer/ExportSelector";
import { DocxReviewer } from "./DocxReviewer";
import { useAnalyze } from "../hooks/useAnalyze";
import {
  useApplyGroup,
  useApplySuggestion,
  useRevertSuggestion,
} from "../hooks/useApplySuggestion";
import { useDocument } from "../hooks/useDocuments";
import { usePatchSuggestion, useSuggestions } from "../hooks/useSuggestions";
import { API_BASE_URL } from "../lib/api";
import { useViewerStore } from "../stores/viewerStore";

export function DocumentReviewer() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const params = useParams();
  const documentId = params.id;

  const document = useDocument(documentId);
  const suggestions = useSuggestions(documentId);
  const analyze = useAnalyze(documentId, document.data);
  const apply = useApplySuggestion(documentId);
  const applyGroup = useApplyGroup(documentId);
  const revert = useRevertSuggestion(documentId);
  const patch = usePatchSuggestion(documentId);

  const pdfVersion = useViewerStore((s) => s.pdfVersion);
  const setPdfVersion = useViewerStore((s) => s.setPdfVersion);
  const currentPage = useViewerStore((s) => s.currentPage);
  const setCurrentPage = useViewerStore((s) => s.setCurrentPage);
  const selectedId = useViewerStore((s) => s.selectedSuggestionId);
  const setSelected = useViewerStore((s) => s.setSelectedSuggestionId);

  // Nombre de pages = metadonnee du document (plus de chargement react-pdf).
  const totalPages = document.data?.page_count ?? 0;

  // Sync the viewer version with the server-side current_version on load.
  useEffect(() => {
    if (document.data) setPdfVersion(document.data.current_version);
  }, [document.data, setPdfVersion]);

  // Image PNG rendue serveur pour la page courante (cf. PdfViewer). `v=`
  // casse le cache apres une edition (nouvelle version du PDF).
  const pageImageUrl = useMemo(() => {
    if (!documentId) return "";
    return `${API_BASE_URL}/documents/${documentId}/pages/${currentPage}.png?dpi=144&v=${pdfVersion}`;
  }, [documentId, currentPage, pdfVersion]);

  if (!documentId) return null;

  // Pipeline Word natif : reviewer dédié (blocs + sortie .docx), le viewer PDF
  // ne s'applique pas. On attend le chargement du document pour connaître le
  // format avant de choisir le reviewer.
  if (document.data?.working_format === "docx") {
    return <DocxReviewer documentId={documentId} />;
  }

  const handleAccept = (id: string): void => {
    patch.mutate(
      { id, status: "accepted" },
      {
        onSuccess: () => apply.mutate(id),
      },
    );
  };

  const handleReject = (id: string): void => {
    patch.mutate({ id, status: "rejected" });
  };

  const handleSaveFeedback = (id: string, feedback: string): void => {
    patch.mutate({ id, status: "rejected", feedback });
  };

  // Annuler un rejet : retour a "open". On NE touche PAS au champ feedback —
  // le motif reste stocke (reutilise si l'anomalie est re-rejetee ensuite).
  const handleUnreject = (id: string): void => {
    patch.mutate({ id, status: "open" });
  };

  const handleSaveEdit = (id: string, newProposed: string): void => {
    patch.mutate(
      { id, status: "edited", proposedText: newProposed },
      {
        onSuccess: () => apply.mutate(id),
      },
    );
  };

  // Apply the same anomaly across every page where it recurs. The
  // backend resolves the group and patches each page in one pass.
  const handleApplyGroup = (id: string): void => {
    applyGroup.mutate(id);
  };

  // Annule une suggestion deja appliquee (revert backend -> version PDF
  // precedente ; cascade les patchs appliques par-dessus).
  const handleUndo = (id: string): void => {
    revert.mutate(id);
  };

  // Barre minimale (demande utilisateur) : Retour | navigation pages | Export.
  // L'analyse se lance depuis la liste Documents ; pas d'unites/suppression ici.
  return (
    <div className="reviewer">
      <div className="reviewer-viewer">
        <div className="reviewer-toolbar">
          <div className="reviewer-toolbar-group">
            <button
              type="button"
              onClick={() => navigate("/documents")}
              className="btn ghost small"
            >
              <ArrowLeft size={14} />
              {t("documents.back")}
            </button>
          </div>

          <div className="reviewer-toolbar-group">
            <button
              type="button"
              onClick={() => setCurrentPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="btn ghost small"
              aria-label={t("viewer.prev")}
            >
              <ChevronLeft size={14} aria-hidden="true" />
            </button>
            <span className="label">
              {currentPage}/{totalPages || "?"}
            </span>
            <button
              type="button"
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={totalPages > 0 && currentPage >= totalPages}
              className="btn ghost small"
              aria-label={t("viewer.next")}
            >
              <ChevronRight size={14} aria-hidden="true" />
            </button>
          </div>

          <div className="reviewer-toolbar-group">
            <AnalysisPageRange
              pageCount={totalPages}
              running={analyze.status === "running"}
              blocked={!analyze.contextReady}
              blockReason={t("reviewer.meta.required")}
              onStart={(range) => void analyze.start(range)}
            />
            {analyze.status === "running" ? (
              <span className="row" style={{ gap: 6, alignItems: "center" }}>
                <span className="progress"><div className="progress-bar" style={{ width: `${analyze.progress}%` }} /></span>
                <span className="label">{analyze.progress}%</span>
              </span>
            ) : null}
            {analyze.status === "error" && analyze.error ? (
              <span className="label" style={{ color: "var(--danger)" }}>{analyze.error}</span>
            ) : null}
            {analyze.warnings.length > 0 ? (
              <span className="badge warn" title={analyze.warnings.join("\n")}>
                {analyze.warnings[0]}
              </span>
            ) : null}
            <ExportSelector documentId={documentId} />
          </div>
        </div>

        <AnalysisTargetBanner />

        <main className="reviewer-canvas reviewer-canvas-stack">
          {document.data ? <DocumentMetaPanel document={document.data} /> : null}
          <PdfViewer
            pageImageUrl={pageImageUrl}
            pageNumber={currentPage}
            suggestions={suggestions.data ?? []}
            selectedSuggestionId={selectedId}
            onSuggestionClick={setSelected}
          />
        </main>
      </div>

      <SuggestionPanel
        suggestions={suggestions.data ?? []}
        selectedId={selectedId}
        onSelect={(id) => {
          setSelected(id);
          const s = suggestions.data?.find((x) => x.id === id);
          if (s) setCurrentPage(s.page);
        }}
        onAccept={handleAccept}
        onReject={handleReject}
        onSaveEdit={handleSaveEdit}
        onSaveFeedback={handleSaveFeedback}
        onUnreject={handleUnreject}
        onApplyGroup={handleApplyGroup}
        onUndo={handleUndo}
      />
    </div>
  );
}
