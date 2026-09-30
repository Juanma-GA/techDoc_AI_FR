import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { useIsMutating } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { QualityBadge } from "../components/QualityBadge";
import { PdfUploadZone } from "../components/upload/PdfUploadZone";
import { AnalysisTargetBanner } from "../components/reviewer/AnalysisTargetBanner";
import { useAnalyze } from "../hooks/useAnalyze";
import { useDeleteDocument, useDocuments, useUploadDocument } from "../hooks/useDocuments";
import { effectiveTarget, useFiltersStore } from "../stores/filtersStore";
import type { Document } from "../types/domain";

// Classes du badge skin (.badge.*) — coherent avec le reste de l'app et le
// preview (au lieu du <Badge> Tailwind de @internal/ui).
const STATUS_BADGE: Record<string, string> = {
  uploaded: "info",
  analyzing: "warn",
  analyzed: "ok",
  edited: "info",
  analysis_failed: "danger",
};

export function DocumentsList() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [autoOpenUploadDialog] = useState(
    () => (location.state as { openUploadDialog?: boolean } | null)?.openUploadDialog === true,
  );
  const docs = useDocuments();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();
  // Nombre d'uploads en cours dans TOUT le cache TanStack Query (pas juste
  // cette instance du hook) : reste correct meme apres avoir navigue puis
  // etre revenu sur cette page pendant qu'un upload tourne encore en fond.
  const uploadingCount = useIsMutating({ mutationKey: ["upload-document"] });
  const isUploading = uploadingCount > 0;
  const targetUnits = useFiltersStore((s) => s.targetUnits);
  const checklistActive = useFiltersStore((s) => s.checklistActive);
  const setChecklistActive = useFiltersStore((s) => s.setChecklistActive);

  useEffect(() => {
    if (!autoOpenUploadDialog) return;
    navigate(`${location.pathname}${location.search}${location.hash}`, {
      replace: true,
      state: null,
    });
  }, [autoOpenUploadDialog, location.hash, location.pathname, location.search, navigate]);

  const handleUpload = (file: File): void => {
    upload.mutate(
      {
        file,
        target: effectiveTarget(targetUnits),
      },
      {
        // Fichier unique -> navigation vers le reviewer ; .zip (batch) -> on
        // reste sur la liste (plusieurs documents crees).
        onSuccess: (res) => {
          if (res && typeof res === "object" && "id" in res) {
            navigate(`/documents/${(res as Document).id}`);
          }
        },
      },
    );
  };

  return (
    <div>
      <PageHeader title={t("documents.title")} subtitle={t("documents.subtitle")} />

      {/* Carte 1 : import (banniere norme active + dropzone). */}
      <section className="card">
        <h2 className="card-title">{t("documents.uploadTitle")}</h2>

        <AnalysisTargetBanner />

        <div className="document-upload-controls">
          {/* Cible checklist : toggle runtime, independant des normes. */}
          {import.meta.env.VITE_LEGACY_RULES_UI === "true" ? <div className="switch-row">
            <div>
              <div>{t("documents.checklistTarget")}</div>
              <div className="label">{t("documents.checklistTargetHint")}</div>
            </div>
            <label className="switch" title={t("documents.checklistTarget")}>
              <input
                type="checkbox"
                checked={checklistActive}
                onChange={(e) => setChecklistActive(e.target.checked)}
              />
              <span className="track" />
            </label>
          </div> : null}

          <div className="form document-upload-form">
            <PdfUploadZone
              onFile={handleUpload}
              uploading={isUploading}
              autoOpen={autoOpenUploadDialog}
            />

            {/* Statut d'import explicite (l'upload est synchrone cote serveur :
                conversion Word->PDF, portail qualite -> plusieurs secondes).
                Base sur le cache global (useIsMutating), donc reste affiche
                meme si on quitte cette page et qu'on y revient pendant l'upload. */}
            {isUploading ? (
              <div
                className="banner"
                role="status"
                aria-live="polite"
                style={{ display: "flex", alignItems: "center", gap: 10 }}
              >
                <span className="spinner" />
                <strong>{t("documents.upload.uploading")}</strong>
              </div>
            ) : null}
            {upload.isError ? (
              <p className="error" role="alert">
                {t("documents.upload.failed", {
                  message: upload.error instanceof Error ? upload.error.message : "",
                })}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {/* Carte 2 : liste des documents importes (bien dissociee de l'import). */}
      <section className="card">
        <h2 className="card-title">{t("documents.listTitle")}</h2>
        {docs.isLoading ? (
          <p className="empty-state">{t("common.loading")}</p>
        ) : docs.data && docs.data.length > 0 ? (
          <div className="item-list">
            {docs.data.map((doc) => (
              <DocRow
                key={doc.id}
                doc={doc}
                onOpen={() => navigate(`/documents/${doc.id}`)}
                onDelete={() => remove.mutate(doc.id)}
              />
            ))}
          </div>
        ) : (
          <p className="empty-state">{t("documents.empty")}</p>
        )}
      </section>
    </div>
  );
}

/**
 * Ligne document (style preview `.doc-row`) avec lancement d'analyse en place :
 * « Lancer l'analyse » declenche le SSE et rafraichit le statut/dashboard sans
 * ouvrir le reviewer.
 */
function DocRow({
  doc,
  onOpen,
  onDelete,
}: {
  doc: Document;
  onOpen: () => void;
  onDelete: () => void;
}): JSX.Element {
  const { t } = useTranslation();
  const analyze = useAnalyze(doc.id, doc);
  const missingContextFields = analyze.missingContextFields;
  const badgeClass = STATUS_BADGE[doc.status] ?? "default";
  const running = analyze.status === "running" || doc.status === "analyzing";

  // Toute la ligne est cliquable (ouvre le detail), comme le preview ; les
  // boutons stoppent la propagation pour garder leur action propre.
  return (
    <div className="item-row clickable" onClick={onOpen}>
      <div className="item-main">
        <p className="item-name">{doc.original_filename}</p>
        <p className="item-meta">
          {doc.page_count} pages · v{doc.current_version} · {doc.target_unit_system}
        </p>
        {doc.quality && doc.quality !== "analyzable" ? (
          <div style={{ marginTop: 6 }}>
            <QualityBadge
              state={doc.quality}
              coverage={doc.text_coverage}
              engine={doc.convert_engine}
            />
          </div>
        ) : null}
        {missingContextFields.length > 0 ? (
          <p className="hint">{t("reviewer.meta.required")}</p>
        ) : null}
        {analyze.status === "running" ? (
          <div className="progress" style={{ marginTop: 6 }}>
            <div className="progress-bar" style={{ width: `${analyze.progress}%` }} />
          </div>
        ) : null}
      </div>

      <span className={`badge ${badgeClass}`}>
        {running ? <span className="spinner" style={{ width: 10, height: 10 }} /> : null}
        {t(`status.${doc.status}`)}
      </span>

      <div className="item-actions" onClick={(e) => e.stopPropagation()}>
        <button type="button" onClick={onOpen} className="btn small primary">
          {t("documents.open")}
        </button>
        <button
          type="button"
          aria-label={t("documents.delete")}
          onClick={onDelete}
          className="btn small danger"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
