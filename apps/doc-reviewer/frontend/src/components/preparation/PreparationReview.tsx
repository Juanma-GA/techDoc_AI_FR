import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { ExportSelector } from "../reviewer/ExportSelector";
import { PreparationReviewPane } from "./PreparationReviewPane";
import { PreparationSkippedRules } from "./PreparationSkippedRules";
import { useClientConfig } from "../../hooks/useClientConfig";
import { useAnalyze } from "../../hooks/useAnalyze";
import {
  useApplySuggestion,
  useRevertSuggestion,
} from "../../hooks/useApplySuggestion";
import {
  useBulkStatus,
  usePatchSuggestion,
  useSuggestions,
} from "../../hooks/useSuggestions";
import { useSyncPreparationAnnotations } from "../../hooks/usePreparation";
import { API_BASE_URL } from "../../lib/api";
import { useViewerStore } from "../../stores/viewerStore";
import { missingDocumentContext, type Document } from "../../types/domain";
import type { PreparationState } from "../../types/preparation";

type Props = {
  document: Document;
  preparation: PreparationState;
};

export function PreparationReview({ document, preparation }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const clientConfig = useClientConfig();
  const analyze = useAnalyze(document.id, document);
  const suggestions = useSuggestions(document.id);
  const apply = useApplySuggestion(document.id);
  const revert = useRevertSuggestion(document.id);
  const patch = usePatchSuggestion(document.id);
  const bulkStatus = useBulkStatus(document.id);
  const syncAnnotations = useSyncPreparationAnnotations(document.id);
  const syncStarted = useRef(false);
  const [suggestionFocusRequest, setSuggestionFocusRequest] = useState(0);
  const pdfVersion = useViewerStore((state) => state.pdfVersion);
  const setPdfVersion = useViewerStore((state) => state.setPdfVersion);
  const currentPage = useViewerStore((state) => state.currentPage);
  const setCurrentPage = useViewerStore((state) => state.setCurrentPage);
  const selectedId = useViewerStore((state) => state.selectedSuggestionId);
  const setSelected = useViewerStore((state) => state.setSelectedSuggestionId);
  const zoom = useViewerStore((state) => state.zoom);
  const setZoom = useViewerStore((state) => state.setZoom);

  const selectedPages = useMemo(
    () =>
      new Set(
        preparation.page_decisions
          .filter((decision) => decision.is_modified === true)
          .map((decision) => decision.page),
      ),
    [preparation.page_decisions],
  );
  const pageOverrides = useMemo(() => {
    const overrides: Record<number, boolean> = {};
    for (let page = 1; page <= document.page_count; page += 1) {
      overrides[page] = selectedPages.has(page);
    }
    return overrides;
  }, [document.page_count, selectedPages]);
  const hasUndecidedPages = preparation.page_decisions.some(
    (decision) => decision.is_modified === null,
  );
  const preparationMetadata = useMemo(() => {
    const metadata = { ...preparation.preparation_mapping };
    for (const [name, field] of Object.entries(clientConfig.data?.mapping.fields ?? {})) {
      if (!Object.prototype.hasOwnProperty.call(metadata, name)) {
        metadata[name] = field.default;
      }
    }
    return metadata;
  }, [clientConfig.data, preparation.preparation_mapping]);
  const requiredContextFields = clientConfig.data
    ? Object.entries(clientConfig.data.mapping.fields)
        .filter(([, field]) => field.required)
        .map(([name]) => name)
    : [];
  const preparationContextReady = Boolean(clientConfig.data) &&
    missingDocumentContext(document, requiredContextFields, preparationMetadata).length === 0;

  useEffect(() => {
    setPdfVersion(document.current_version);
    setCurrentPage(1);
  }, [document.id, document.current_version, setCurrentPage, setPdfVersion]);

  useEffect(() => {
    if (analyze.status === "running") {
      syncStarted.current = false;
    } else if (analyze.status === "done" && !syncStarted.current) {
      syncStarted.current = true;
      syncAnnotations.mutate();
    }
  }, [analyze.status, syncAnnotations]);

  const pageImageUrl = `${API_BASE_URL}/documents/${document.id}/pages/${currentPage}.png?dpi=144&v=${pdfVersion}`;

  const accept = (id: string): void => {
    patch.mutate({ id, status: "accepted" }, { onSuccess: () => apply.mutate(id) });
  };
  const reject = (id: string): void => patch.mutate({ id, status: "rejected" });
  const saveFeedback = (id: string, feedback: string): void =>
    patch.mutate({ id, status: "rejected", feedback });
  const unreject = (id: string): void => patch.mutate({ id, status: "open" });
  const saveEdit = (id: string, proposedText: string): void => {
    patch.mutate(
      { id, status: "edited", proposedText },
      { onSuccess: () => apply.mutate(id) },
    );
  };

  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 className="card-title">{t("preparation.reviewTitle")}</h2>
          <p className="card-sub">{t("preparation.reviewHint")}</p>
        </div>
        <span className="badge info">
          {t("preparation.modified")}: {selectedPages.size}
        </span>
      </div>
      {analyze.status === "error" && analyze.error ? (
        <p className="error" role="alert">
          {t("preparation.analysisError", { message: analyze.error })}
        </p>
      ) : null}
      {analyze.warnings.length > 0 ? (
        <p className="banner warn" role="status">{analyze.warnings.join(" · ")}</p>
      ) : null}
      {syncAnnotations.isError ? (
        <p className="error" role="alert">
          {syncAnnotations.error instanceof Error ? syncAnnotations.error.message : ""}
        </p>
      ) : null}
      <PreparationSkippedRules rules={preparation.skipped_rules ?? []} />
      <div className="row" style={{ gap: 8, flexWrap: "wrap", margin: "12px 0" }}>
        <button
          type="button"
          className="btn ghost small"
          onClick={() => navigate("/preparation")}
        >
          <ArrowLeft size={14} aria-hidden="true" />
          {t("preparation.back")}
        </button>
        <span className="label">
          {t("viewer.page", { page: currentPage, total: document.page_count })}
        </span>
        <button
          type="button"
          className="btn ghost small"
          disabled={currentPage <= 1}
          onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
          aria-label={t("viewer.prev")}
        >
          <ChevronLeft size={14} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="btn ghost small"
          disabled={currentPage >= document.page_count}
          onClick={() => setCurrentPage(Math.min(document.page_count, currentPage + 1))}
          aria-label={t("viewer.next")}
        >
          <ChevronRight size={14} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="btn ghost small"
          onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
          disabled={zoom <= 0.5}
          aria-label={t("reviewer.toolbar.zoomOut")}
        >
          <ZoomOut size={14} aria-hidden="true" />
        </button>
        <span className="label">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          className="btn ghost small"
          onClick={() => setZoom(Math.min(3, zoom + 0.25))}
          disabled={zoom >= 3}
          aria-label={t("reviewer.toolbar.zoomIn")}
        >
          <ZoomIn size={14} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="btn primary small"
          disabled={
            analyze.status === "running" ||
            selectedPages.size === 0 ||
            hasUndecidedPages ||
            !preparationContextReady
          }
          title={!preparationContextReady ? t("reviewer.meta.required") : undefined}
          onClick={() =>
            void analyze.start({
              modifiedOnly: true,
              preparationContext: true,
              contextReadyOverride: preparationContextReady,
              pageOverrides,
            })
          }
        >
          {analyze.status === "running"
            ? t("preparation.runningVerification")
            : t("preparation.runVerification")}
        </button>
        <ExportSelector documentId={document.id} />
      </div>
      {hasUndecidedPages ? <p className="hint">{t("preparation.resolvePages")}</p> : null}
      <PreparationReviewPane
        pageImageUrl={pageImageUrl}
        pageNumber={currentPage}
        zoom={zoom}
        suggestions={suggestions.data ?? []}
        selectedId={selectedId}
        focusRequest={suggestionFocusRequest}
        onSuggestionClick={(id) => {
          setSelected(id);
          setSuggestionFocusRequest((request) => request + 1);
        }}
        onSelect={(id) => {
          setSelected(id);
          const suggestion = suggestions.data?.find((item) => item.id === id);
          if (suggestion) setCurrentPage(suggestion.page);
        }}
        onAccept={accept}
        onReject={reject}
        onRejectAll={(ids) => bulkStatus.mutate({ ids, status: "rejected" })}
        onSaveEdit={saveEdit}
        onSaveFeedback={saveFeedback}
        onUnreject={unreject}
        onUndo={(id) => revert.mutate(id)}
      />
    </section>
  );
}
