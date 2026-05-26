import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { PdfViewer } from "../components/reviewer/PdfViewer";
import { ReviewerToolbar } from "../components/reviewer/ReviewerToolbar";
import { SuggestionPanel } from "../components/reviewer/SuggestionPanel";
import { useAnalyze } from "../hooks/useAnalyze";
import { useApplyGroup, useApplySuggestion } from "../hooks/useApplySuggestion";
import { useDocument } from "../hooks/useDocuments";
import { usePatchSuggestion, useSuggestions } from "../hooks/useSuggestions";
import { API_BASE_URL } from "../lib/api";
import { useViewerStore } from "../stores/viewerStore";

export function DocumentReviewer() {
  const params = useParams();
  const documentId = params.id;

  const document = useDocument(documentId);
  const suggestions = useSuggestions(documentId);
  const apply = useApplySuggestion(documentId);
  const applyGroup = useApplyGroup(documentId);
  const patch = usePatchSuggestion(documentId);
  const analyze = useAnalyze(documentId);

  const pdfVersion = useViewerStore((s) => s.pdfVersion);
  const setPdfVersion = useViewerStore((s) => s.setPdfVersion);
  const currentPage = useViewerStore((s) => s.currentPage);
  const setCurrentPage = useViewerStore((s) => s.setCurrentPage);
  const zoom = useViewerStore((s) => s.zoom);
  const setZoom = useViewerStore((s) => s.setZoom);
  const selectedId = useViewerStore((s) => s.selectedSuggestionId);
  const setSelected = useViewerStore((s) => s.setSelectedSuggestionId);

  const [totalPages, setTotalPages] = useState(0);

  // Sync the viewer version with the server-side current_version on load.
  useEffect(() => {
    if (document.data) setPdfVersion(document.data.current_version);
  }, [document.data, setPdfVersion]);

  const pdfUrl = useMemo(() => {
    if (!documentId) return "";
    return `${API_BASE_URL}/documents/${documentId}/pdf?v=${pdfVersion}`;
  }, [documentId, pdfVersion]);

  if (!documentId) return null;

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

  const handleExport = (): void => {
    if (!document.data) return;
    const url = `${API_BASE_URL}/documents/${documentId}/export`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="flex h-screen flex-col">
      <ReviewerToolbar
        filename={document.data?.original_filename ?? "—"}
        version={pdfVersion}
        zoom={zoom}
        page={currentPage}
        totalPages={totalPages}
        analyzeStatus={analyze.status}
        onZoomIn={() => setZoom(zoom + 0.1)}
        onZoomOut={() => setZoom(zoom - 0.1)}
        onPrev={() => setCurrentPage(currentPage - 1)}
        onNext={() => setCurrentPage(currentPage + 1)}
        onAnalyze={analyze.start}
        onExport={handleExport}
      />

      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 items-start justify-center overflow-auto bg-bg-3 p-4">
          <PdfViewer
            pdfUrl={pdfUrl}
            pageNumber={currentPage}
            zoom={zoom}
            suggestions={suggestions.data ?? []}
            selectedSuggestionId={selectedId}
            onSuggestionClick={setSelected}
            onTotalPages={setTotalPages}
          />
        </main>
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
          onApplyGroup={handleApplyGroup}
        />
      </div>
    </div>
  );
}
