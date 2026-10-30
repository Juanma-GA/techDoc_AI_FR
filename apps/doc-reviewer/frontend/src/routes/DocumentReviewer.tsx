import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  CircleMinus,
  Maximize2,
  Paperclip,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { PdfViewer } from "../components/reviewer/PdfViewer";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { IncompleteChecksNotice } from "../components/reviewer/IncompleteChecksNotice";
import { AnalysisTargetBanner } from "../components/reviewer/AnalysisTargetBanner";
import { AnalysisPageRange } from "../components/reviewer/AnalysisPageRange";
import { NormChoiceDialog, type NormChoice } from "../components/reviewer/NormChoiceDialog";
import { DocumentMetaPanel } from "../components/reviewer/DocumentMetaPanel";
import { SuggestionPanel } from "../components/reviewer/SuggestionPanel";
import { ExportSelector } from "../components/reviewer/ExportSelector";
import { DocxReviewer } from "./DocxReviewer";
import { useAnalyze, type AnalyzeOptions } from "../hooks/useAnalyze";
import {
  useApplySuggestion,
  useRevertSuggestion,
} from "../hooks/useApplySuggestion";
import { useClientRules, usePatchClientRuleBundle } from "../hooks/useClientConfig";
import { useDocument } from "../hooks/useDocuments";
import {
  activeRuleCounts,
  normNeedsChoice,
  useDocumentNorm,
  type DocumentNorm,
} from "../hooks/useDocumentNorm";
import {
  useBulkStatus,
  usePatchSuggestion,
  useRuleResults,
  useSuggestions,
} from "../hooks/useSuggestions";
import { API_BASE_URL } from "../lib/api";
import { useViewerStore } from "../stores/viewerStore";

export function DocumentReviewer() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const params = useParams();
  const documentId = params.id;

  const document = useDocument(documentId);
  const suggestions = useSuggestions(documentId);
  const ruleResults = useRuleResults(
    document.data?.working_format === "pdf" ? documentId : undefined,
  );
  const analyze = useAnalyze(documentId, document.data);
  const clientRules = useClientRules();
  const patchRuleBundle = usePatchClientRuleBundle();
  const documentNorm = useDocumentNorm(documentId, document.data?.working_format === "pdf");
  const [normPrompt, setNormPrompt] = useState<{
    range: AnalyzeOptions;
    detection: DocumentNorm;
  } | null>(null);
  const [normNotice, setNormNotice] = useState<string | null>(null);
  const [pendingPageStatus, setPendingPageStatus] = useState<{
    page: number;
    isModified: boolean | null;
    requiresChoice: boolean;
  } | null>(null);
  const [activeReviewPage, setActiveReviewPage] = useState<number | null>(null);
  const [pageReviewChoices, setPageReviewChoices] = useState<Record<number, boolean>>({});
  const apply = useApplySuggestion(documentId);
  const revert = useRevertSuggestion(documentId);
  const patch = usePatchSuggestion(documentId);
  const bulkStatus = useBulkStatus(documentId);

  const pdfVersion = useViewerStore((s) => s.pdfVersion);
  const setPdfVersion = useViewerStore((s) => s.setPdfVersion);
  const currentPage = useViewerStore((s) => s.currentPage);
  const setCurrentPage = useViewerStore((s) => s.setCurrentPage);
  const currentPageStatus = analyze.pageStatuses.find((page) => page.page === currentPage);
  const pagesToReview = analyze.pageStatuses.filter(
    (page) => page.requires_review && page.is_modified === null,
  );
  const remainingPagesToReview = pagesToReview.filter(
    (page) => !Object.prototype.hasOwnProperty.call(pageReviewChoices, page.page),
  );
  const nextReviewPage = remainingPagesToReview[0];
  const reviewFlowActive = activeReviewPage !== null || Object.keys(pageReviewChoices).length > 0;
  const selectedId = useViewerStore((s) => s.selectedSuggestionId);
  const setSelected = useViewerStore((s) => s.setSelectedSuggestionId);
  const [suggestionFocusRequest, setSuggestionFocusRequest] = useState(0);
  const zoom = useViewerStore((s) => s.zoom);
  const setZoom = useViewerStore((s) => s.setZoom);

  // Nombre de pages = metadonnee du document (plus de chargement react-pdf).
  const totalPages = document.data?.page_count ?? 0;

  // Sync the viewer version with the server-side current_version on load.
  useEffect(() => {
    if (document.data) setPdfVersion(document.data.current_version);
  }, [document.data, setPdfVersion]);

  useEffect(() => {
    setActiveReviewPage(null);
    setPageReviewChoices({});
  }, [documentId]);

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

  // Annule une suggestion deja appliquee (revert backend -> version PDF
  // precedente ; cascade les patchs appliques par-dessus).
  const handleUndo = (id: string): void => {
    revert.mutate(id);
  };

  // Detection is advisory: when it fails the analysis starts as before.
  const startAnalysis = async (range: AnalyzeOptions): Promise<void> => {
    setNormNotice(null);
    let detection: DocumentNorm | undefined;
    try {
      detection = (await documentNorm.refetch()).data;
    } catch {
      detection = undefined;
    }
    if (detection && normNeedsChoice(detection, clientRules.data)) {
      setNormPrompt({ range, detection });
      return;
    }
    await analyze.start(range);
  };

  const confirmNorm = async ({ norm, persist }: NormChoice): Promise<void> => {
    const prompt = normPrompt;
    if (!prompt) return;
    setNormPrompt(null);
    if (persist && clientRules.data) {
      const verification = clientRules.data.filter((rule) => rule.scope === "verification");
      const normCodes = prompt.detection.norms.map((item) => item.code);
      try {
        await patchRuleBundle.mutateAsync({
          rules: verification.filter((rule) => rule.bundle_code === norm),
          active: true,
        });
        await patchRuleBundle.mutateAsync({
          rules: verification.filter(
            (rule) => rule.bundle_code !== norm && normCodes.includes(rule.bundle_code),
          ),
          active: false,
        });
      } catch {
        setNormNotice(t("reviewer.norm.persistFailed"));
      }
    }
    await analyze.start({ ...prompt.range, norm });
  };

  const handlePageReviewChoice = (isModified: boolean): void => {
    if (activeReviewPage === null) return;
    const nextChoices = { ...pageReviewChoices, [activeReviewPage]: isModified };
    const hasRemainingPages = pagesToReview.some(
      (page) => !Object.prototype.hasOwnProperty.call(nextChoices, page.page),
    );
    setActiveReviewPage(null);
    if (hasRemainingPages) {
      setPageReviewChoices(nextChoices);
    } else {
      setPageReviewChoices({});
      analyze.correctPageStatuses(nextChoices);
    }
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

          <div className="reviewer-toolbar-group reviewer-zoom-controls" aria-label={t("reviewer.toolbar.fit")}>
            <button
              type="button"
              className="btn ghost small"
              onClick={() => setZoom(zoom - 0.25)}
              disabled={zoom <= 0.5}
              aria-label={t("reviewer.toolbar.zoomOut")}
              title={t("reviewer.toolbar.zoomOut")}
            >
              <ZoomOut size={14} aria-hidden="true" />
            </button>
            <span className="label reviewer-zoom-value">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              className="btn ghost small"
              onClick={() => setZoom(zoom + 0.25)}
              disabled={zoom >= 3}
              aria-label={t("reviewer.toolbar.zoomIn")}
              title={t("reviewer.toolbar.zoomIn")}
            >
              <ZoomIn size={14} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="btn ghost small"
              onClick={() => setZoom(1)}
              aria-label={t("reviewer.toolbar.fit")}
              title={t("reviewer.toolbar.fit")}
            >
              <Maximize2 size={14} aria-hidden="true" />
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
            {currentPageStatus ? (
              <button
                type="button"
                className="btn ghost small"
                disabled={analyze.status === "running" || reviewFlowActive}
                onClick={() => {
                  const requiresChoice = currentPageStatus.is_modified === null;
                  setPendingPageStatus({
                    page: currentPage,
                    isModified: requiresChoice ? null : !currentPageStatus.is_modified,
                    requiresChoice,
                  });
                }}
              >
                {currentPageStatus.is_modified === true ? (
                  <CircleCheck size={14} aria-hidden="true" />
                ) : currentPageStatus.is_modified === false ? (
                  <CircleMinus size={14} aria-hidden="true" />
                ) : (
                  <CircleHelp size={14} aria-hidden="true" />
                )}
                {currentPageStatus.is_modified === true
                  ? t("reviewer.pageStatus.modified")
                  : currentPageStatus.is_modified === false
                    ? t("reviewer.pageStatus.unchanged")
                    : t("reviewer.pageStatus.unknown")}
                {currentPageStatus.source === "manual" ? (
                  <span className="hint">({t("reviewer.pageStatus.manual")})</span>
                ) : null}
              </button>
            ) : null}
          </div>

          <div className="reviewer-toolbar-group reviewer-toolbar-actions">
            <div
              className="row"
              style={{ gap: 6, alignItems: "center", minWidth: 0, gridColumn: "1 / -1" }}
            >
              <button
                type="button"
                className="btn ghost small"
                aria-disabled="true"
                title={t("reviewer.previousRevision.unavailable")}
                aria-label={`${t("reviewer.previousRevision.attach")}. ${t("reviewer.previousRevision.unavailable")}`}
              >
                <Paperclip size={14} aria-hidden="true" />
                {t("reviewer.previousRevision.attach")}
              </button>
            </div>
            <AnalysisPageRange
              pageCount={totalPages}
              running={analyze.status === "running"}
              blocked={!analyze.contextReady}
              blockReason={t("reviewer.meta.required")}
              trackModifiedPages={documentNorm.data?.page_revision_tracking ?? true}
              onStart={(range) => void startAnalysis(range)}
            />
            {analyze.status === "running" ? (
              <span className="row" style={{ gap: 6, alignItems: "center" }}>
                <span className="progress">
                  <div
                    className={`progress-bar${analyze.progressIndeterminate ? " indeterminate" : ""}`}
                    style={analyze.progressIndeterminate ? undefined : { width: `${analyze.progress}%` }}
                  />
                </span>
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
            {normNotice ? <span className="badge warn">{normNotice}</span> : null}
            <ExportSelector documentId={documentId} />
          </div>
        </div>

        <AnalysisTargetBanner />
        {remainingPagesToReview.length > 0 ? (
          <section className="banner warn" role="status" aria-live="polite">
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
              <span>
                {t("reviewer.pageStatus.reviewNotice", {
                  pages: remainingPagesToReview.map((page) => page.page).join(", "),
                })}
              </span>
              {activeReviewPage !== null ? (
                <div className="row" role="group" aria-label={t("reviewer.pageStatus.chooseLabel")}>
                  <span className="label">
                    {t("reviewer.pageStatus.chooseTitle", { page: activeReviewPage })}
                  </span>
                  <button
                    type="button"
                    className="btn secondary small"
                    disabled={analyze.status === "running"}
                    onClick={() => handlePageReviewChoice(true)}
                  >
                    <CircleCheck size={14} aria-hidden="true" />
                    {t("reviewer.pageStatus.modified")}
                  </button>
                  <button
                    type="button"
                    className="btn secondary small"
                    disabled={analyze.status === "running"}
                    onClick={() => handlePageReviewChoice(false)}
                  >
                    <CircleMinus size={14} aria-hidden="true" />
                    {t("reviewer.pageStatus.unchanged")}
                  </button>
                </div>
              ) : nextReviewPage ? (
                <button
                  type="button"
                  className="btn secondary small"
                  disabled={analyze.status === "running"}
                  onClick={() => {
                    setCurrentPage(nextReviewPage.page);
                    setActiveReviewPage(nextReviewPage.page);
                  }}
                >
                  {t("reviewer.pageStatus.reviewNext", { page: nextReviewPage.page })}
                </button>
              ) : null}
            </div>
          </section>
        ) : null}
        <IncompleteChecksNotice
          results={ruleResults.data ?? []}
          isRunning={analyze.status === "running"}
        />

        <main className="reviewer-canvas reviewer-canvas-stack">
          {document.data ? <DocumentMetaPanel document={document.data} /> : null}
          <PdfViewer
            pageImageUrl={pageImageUrl}
            pageNumber={currentPage}
            zoom={zoom}
            suggestions={suggestions.data ?? []}
            selectedSuggestionId={selectedId}
            onSuggestionClick={(id) => {
              setSelected(id);
              setSuggestionFocusRequest((request) => request + 1);
            }}
          />
        </main>
      </div>

      <SuggestionPanel
        suggestions={suggestions.data ?? []}
        selectedId={selectedId}
        focusRequest={suggestionFocusRequest}
        onSelect={(id) => {
          setSelected(id);
          const s = suggestions.data?.find((x) => x.id === id);
          if (s) setCurrentPage(s.page);
        }}
        onAccept={handleAccept}
        onReject={handleReject}
        onRejectAll={(ids) => bulkStatus.mutate({ ids, status: "rejected" })}
        onSaveEdit={handleSaveEdit}
        onSaveFeedback={handleSaveFeedback}
        onUnreject={handleUnreject}
        onUndo={handleUndo}
      />
      <ConfirmDialog
        open={pendingPageStatus !== null}
        onOpenChange={(open) => {
          if (!open) setPendingPageStatus(null);
        }}
        title={
          pendingPageStatus?.requiresChoice
            ? t("reviewer.pageStatus.chooseTitle", { page: pendingPageStatus.page })
            : t("reviewer.pageStatus.confirmTitle")
        }
        description={
          pendingPageStatus
            ? pendingPageStatus.isModified === null
              ? t("reviewer.pageStatus.chooseDescription")
              : pendingPageStatus.isModified
                ? t("reviewer.pageStatus.confirmModified", { page: pendingPageStatus.page })
                : t("reviewer.pageStatus.confirmUnchanged", { page: pendingPageStatus.page })
            : undefined
        }
        confirmLabel={t("common.confirm")}
        cancelLabel={t("common.cancel")}
        confirmDisabled={pendingPageStatus?.isModified === null}
        onConfirm={() => {
          if (pendingPageStatus?.isModified !== null && pendingPageStatus) {
            analyze.correctPageStatus(pendingPageStatus.page, pendingPageStatus.isModified);
          }
        }}
      >
        {pendingPageStatus?.requiresChoice ? (
          <div className="row" role="group" aria-label={t("reviewer.pageStatus.chooseLabel")}>
            <button
              type="button"
              className={pendingPageStatus.isModified === true ? "btn primary small" : "btn secondary small"}
              aria-pressed={pendingPageStatus.isModified === true}
              onClick={() =>
                setPendingPageStatus((current) =>
                  current ? { ...current, isModified: true } : null,
                )
              }
            >
              <CircleCheck size={14} aria-hidden="true" />
              {t("reviewer.pageStatus.modified")}
            </button>
            <button
              type="button"
              className={pendingPageStatus.isModified === false ? "btn primary small" : "btn secondary small"}
              aria-pressed={pendingPageStatus.isModified === false}
              onClick={() =>
                setPendingPageStatus((current) =>
                  current ? { ...current, isModified: false } : null,
                )
              }
            >
              <CircleMinus size={14} aria-hidden="true" />
              {t("reviewer.pageStatus.unchanged")}
            </button>
          </div>
        ) : null}
      </ConfirmDialog>
      {normPrompt ? (
        <NormChoiceDialog
          detection={normPrompt.detection}
          activeCounts={activeRuleCounts(clientRules.data ?? [], normPrompt.detection.norms)}
          onCancel={() => setNormPrompt(null)}
          onConfirm={(choice) => void confirmNorm(choice)}
        />
      ) : null}
    </div>
  );
}
