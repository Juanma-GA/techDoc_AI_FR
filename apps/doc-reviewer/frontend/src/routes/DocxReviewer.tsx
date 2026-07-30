import { ArrowLeft, Download } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { SuggestionPanel } from "../components/reviewer/SuggestionPanel";
import {
  useApplyGroup,
  useApplySuggestion,
  useRevertSuggestion,
} from "../hooks/useApplySuggestion";
import { useDocxBlocks, useDocument } from "../hooks/useDocuments";
import { usePatchSuggestion, useSuggestions } from "../hooks/useSuggestions";
import { API_BASE_URL } from "../lib/api";
import { useViewerStore } from "../stores/viewerStore";

/**
 * Reviewer du pipeline Word natif (Phase 1). Word est en flux (pas de
 * géométrie) : on affiche la liste des blocs `dp<N>` à gauche (les blocs
 * porteurs d'une anomalie sont surlignés) et le panneau de suggestions à
 * droite (réutilisé du reviewer PDF). L'export rend le `.docx` corrigé.
 */
export function DocxReviewer({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const document = useDocument(documentId);
  const blocks = useDocxBlocks(documentId, true);
  const suggestions = useSuggestions(documentId);
  const apply = useApplySuggestion(documentId);
  const applyGroup = useApplyGroup(documentId);
  const revert = useRevertSuggestion(documentId);
  const patch = usePatchSuggestion(documentId);

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
  const handleApplyGroup = (id: string): void => {
    applyGroup.mutate(id);
  };
  const handleUndo = (id: string): void => {
    revert.mutate(id);
  };

  const handleExport = (): void => {
    if (!document.data) return;
    // Rend le .docx corrigé (version courante).
    window.open(`${API_BASE_URL}/documents/${documentId}/export`, "_blank", "noopener,noreferrer");
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
          <div className="reviewer-toolbar-group">
            <button type="button" onClick={handleExport} className="btn primary small">
              <Download size={14} />
              {t("reviewer.toolbar.exportDocx")}
            </button>
          </div>
        </div>

        <main className="reviewer-canvas" style={{ overflow: "auto", padding: 16 }}>
          {blocks.isLoading ? (
            <p className="hint">{t("common.loading")}</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 900 }}>
              {(blocks.data?.blocks ?? []).map((b) => {
                const count = byTarget.get(b.target_id) ?? 0;
                const isSelected = selectedTarget === b.target_id;
                return (
                  <div
                    key={b.target_id}
                    style={{
                      padding: "6px 10px",
                      borderRadius: 6,
                      border: `1px solid ${isSelected ? "var(--brand-light)" : "var(--border)"}`,
                      background: count > 0 ? "var(--card-hover)" : "var(--bg-2)",
                      fontFamily:
                        b.kind === "heading" ? '"Orbitron", sans-serif' : "inherit",
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
        onSaveEdit={handleSaveEdit}
        onSaveFeedback={handleSaveFeedback}
        onUnreject={handleUnreject}
        onApplyGroup={handleApplyGroup}
        onUndo={handleUndo}
      />
    </div>
  );
}
