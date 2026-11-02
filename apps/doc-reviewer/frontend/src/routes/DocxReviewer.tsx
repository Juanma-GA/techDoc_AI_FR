import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { SuggestionPanel } from "../components/reviewer/SuggestionPanel";
import { ExportSelector } from "../components/reviewer/ExportSelector";
import { AnalysisTargetBanner } from "../components/reviewer/AnalysisTargetBanner";
import { AnalysisPageRange } from "../components/reviewer/AnalysisPageRange";
import { DocumentMetaPanel } from "../components/reviewer/DocumentMetaPanel";
import { IncompleteChecksNotice } from "../components/reviewer/IncompleteChecksNotice";
import { useAnalyze } from "../hooks/useAnalyze";
import {
  useApplySuggestion,
  useRevertSuggestion,
} from "../hooks/useApplySuggestion";
import { useDocxBlocks, useDocument } from "../hooks/useDocuments";
import {
  useBulkStatus,
  usePatchSuggestion,
  useRuleResults,
  useSuggestions,
} from "../hooks/useSuggestions";
import { useViewerStore } from "../stores/viewerStore";

/**
 * Reviewer du pipeline Word natif (Phase 1). Word est en flux (pas de
 * géométrie) : on affiche la liste des blocs `dp<N>` à gauche (les blocs
 * porteurs d'une anomalie sont surlignés) et le panneau de suggestions à
 * droite (réutilisé du reviewer PDF). L'export rend le `.docx` corrigé.
 */
export function DocxReviewer({
  documentId,
}: { documentId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const document = useDocument(documentId);
  const blocks = useDocxBlocks(documentId, true);
  const suggestions = useSuggestions(documentId);
  const ruleResults = useRuleResults(documentId);
  const analyze = useAnalyze(documentId, document.data);
  const apply = useApplySuggestion(documentId);
  const revert = useRevertSuggestion(documentId);
  const patch = usePatchSuggestion(documentId);
  const bulkStatus = useBulkStatus(documentId);

  const selectedId = useViewerStore((s) => s.selectedSuggestionId);
  const setSelected = useViewerStore((s) => s.setSelectedSuggestionId);

  // target_id -> anomalies non rejetées portées par ce bloc.
  const byTarget = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of suggestions.data ?? []) {
      if (s.target_id && s.status !== "rejected") {
        map.set(s.target_id, (map.get(s.target_id) ?? 0) + 1);
      }
    }
    return map;
  }, [suggestions.data]);

  const selectedTarget = useMemo(
    () => suggestions.data?.find((s) => s.id === selectedId)?.target_id ?? null,
    [suggestions.data, selectedId],
  );

  // Navigue jusqu'au bloc porteur de l'anomalie selectionnee (clic depuis le
  // panneau de suggestions) : fait defiler la liste des blocs jusqu'a lui.
  const blocksListRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!selectedTarget || !blocksListRef.current) return;
    const el = blocksListRef.current.querySelector<HTMLElement>(
      `[data-target-id="${selectedTarget}"]`,
    );
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedTarget]);

  const handleAccept = (id: string): void => {
    patch.mutate({ id, status: "accepted" }, { onSuccess: () => apply.mutate(id) });
  };
  const handleReject = (id: string): void => {
    patch.mutate({ id, status: "rejected" });
  };
  const handleSaveFeedback = (id: string, feedback: string): void => {
    patch.mutate({ id, status: "rejected", feedback });
  };
  const handleUnreject = (id: string): void => {
    patch.mutate({ id, status: "open" });
  };
  const handleSaveEdit = (id: string, newProposed: string): void => {
    patch.mutate(
      { id, status: "edited", proposedText: newProposed },
      { onSuccess: () => apply.mutate(id) },
    );
  };
  const handleUndo = (id: string): void => {
    revert.mutate(id);
  };

  return (
    <div className="reviewer">
      <div className="reviewer-viewer">
        <div className="reviewer-toolbar">
          <div className="reviewer-toolbar-group">
            <button type="button" onClick={() => navigate("/documents")} className="btn ghost small">
              <ArrowLeft size={14} />
              {t("documents.back")}
            </button>
            <span className="badge info">{t("reviewer.docxMode")}</span>
          </div>
          <div className="reviewer-toolbar-group reviewer-toolbar-actions">
            <AnalysisPageRange
              pageCount={document.data?.page_count ?? 0}
              running={analyze.status === "running"}
              blocked={!analyze.contextReady}
              blockReason={t("reviewer.meta.required")}
              onStart={(range) => void analyze.start(range)}
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
            <ExportSelector documentId={documentId} />
          </div>
        </div>

        <AnalysisTargetBanner />
        <IncompleteChecksNotice
          results={ruleResults.data ?? []}
          isRunning={analyze.status === "running"}
        />

        <main className="reviewer-canvas reviewer-canvas-stack" style={{ overflow: "auto", padding: 16 }}>
          {document.data ? <DocumentMetaPanel document={document.data} /> : null}
          {blocks.isLoading ? (
            <p className="hint">{t("common.loading")}</p>
          ) : (
            <div
              ref={blocksListRef}
              style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 900 }}
            >
              {(blocks.data?.blocks ?? []).map((b) => {
                const count = byTarget.get(b.target_id) ?? 0;
                const isSelected = selectedTarget === b.target_id;
                return (
                  <div
                    key={b.target_id}
                    data-target-id={b.target_id}
                    style={{
                      padding: "6px 10px",
                      borderRadius: 6,
                      border: `1px solid ${isSelected ? "var(--brand-light)" : "var(--border)"}`,
                      background: count > 0 ? "var(--card-hover)" : "var(--bg-2)",
                      fontFamily:
                        b.kind === "heading" ? "var(--font-display)" : "inherit",
                    }}
                  >
                    <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                      <span className="label" style={{ minWidth: 44, color: "var(--fg-dim)" }}>
                        {b.zone === "body" ? `p.${b.page}` : b.zone}
                      </span>
                      <span style={{ flex: 1 }}>{b.text}</span>
                      {b.semantic_zone &&
                      !["body", "header", "footer"].includes(b.semantic_zone) ? (
                        <span className="badge info" title={t("reviewer.docxZone")}>
                          {b.semantic_zone}
                        </span>
                      ) : null}
                      {b.revised ? (
                        <span className="badge warn" title={t("reviewer.docxRevised")}>
                          {t("reviewer.docxRevisedBadge")}
                        </span>
                      ) : null}
                      {count > 0 ? <span className="badge danger">{count}</span> : null}
                    </div>
                    {b.table_label ? (
                      <div className="label" style={{ color: "var(--fg-dim)", marginTop: 2 }}>
                        {b.table_label}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </main>
      </div>

      <SuggestionPanel
        suggestions={suggestions.data ?? []}
        selectedId={selectedId}
        onSelect={setSelected}
        onAccept={handleAccept}
        onReject={handleReject}
        onRejectAll={(ids) => bulkStatus.mutate({ ids, status: "rejected" })}
        onSaveEdit={handleSaveEdit}
        onSaveFeedback={handleSaveFeedback}
        onUnreject={handleUnreject}
        onUndo={handleUndo}
      />
    </div>
  );
}
