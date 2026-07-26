import { Play, Trash2 } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { PdfUploadZone } from "../components/upload/PdfUploadZone";
import { useAnalyze } from "../hooks/useAnalyze";
import { useDeleteDocument, useDocuments, useUploadDocument } from "../hooks/useDocuments";
import { useStandards } from "../hooks/useStandards";
import { effectiveTarget, useFiltersStore } from "../stores/filtersStore";
import type { Document } from "../types/domain";

// Selection MULTIPLE : metric et/ou imperial (vide ou les deux => "auto").
const TARGET_UNITS: ("metric" | "imperial")[] = ["metric", "imperial"];

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
  const navigate = useNavigate();
  const docs = useDocuments();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();
  const standards = useStandards();
  const targetUnits = useFiltersStore((s) => s.targetUnits);
  const toggleTargetUnit = useFiltersStore((s) => s.toggleTargetUnit);
  const checklistActive = useFiltersStore((s) => s.checklistActive);
  const setChecklistActive = useFiltersStore((s) => s.setChecklistActive);
  const activeStandardVersionIds = useFiltersStore((s) => s.activeStandardVersionIds);

  // Bandeau "Normes cibles actives" (preview 289-293) : libelles des versions
  // actives selectionnees dans Parametres. Le choix du standard ne se fait plus
  // a l'upload (parite preview) — juste ici en lecture.
  const activeStandardLabel = useMemo(() => {
    const items = standards.data ?? [];
    const labels: string[] = [];
    for (const std of items) {
      for (const v of std.versions) {
        if (activeStandardVersionIds.includes(v.id)) labels.push(`${std.code} ${v.label}`);
      }
    }
    return labels.length > 0 ? labels.join(" · ") : null;
  }, [standards.data, activeStandardVersionIds]);

  const handleUpload = (file: File): void => {
    upload.mutate(
      { file, target: effectiveTarget(targetUnits), standardVersionIds: activeStandardVersionIds },
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

      {/* Carte 1 : import (banniere norme active + slicer unites + dropzone). */}
      <section className="card">
        <h2 className="card-title">{t("documents.uploadTitle")}</h2>

        <div className="banner">
          <span>{t("documents.activeStandardLabel")}</span>
          <strong className="label">
            {activeStandardLabel ?? t("standards.transverse")}
          </strong>
          <Link to="/settings" className="grow" style={{ textAlign: "right" }}>
            {t("documents.changeStandard")}
          </Link>
        </div>

        {/* Cible checklist : toggle runtime, independant des normes. */}
        <div className="switch-row">
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
        </div>

        <div className="form">
          <div className="field">
            <span className="field-label">{t("documents.targetUnit")}</span>
            <div className="slicer">
              {TARGET_UNITS.map((unit) => {
                const on = targetUnits.includes(unit);
                return (
                  <button
                    key={unit}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleTargetUnit(unit)}
                    className={on ? "slicer-pill active" : "slicer-pill"}
                  >
                    {t(`settings.targetUnit.${unit}`)}
                  </button>
                );
              })}
              <span className="label" style={{ alignSelf: "center", marginLeft: 6 }}>
                {targetUnits.length === 1 ? "" : t("settings.targetUnit.auto")}
              </span>
            </div>
          </div>

          <PdfUploadZone onFile={handleUpload} disabled={upload.isPending} />
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
  const analyze = useAnalyze(doc.id);
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
        <button
          type="button"
          onClick={() => void analyze.start()}
          disabled={running}
          className="btn small secondary"
        >
          <Play size={14} />
          {running ? t("reviewer.toolbar.analyzing") : t("reviewer.toolbar.analyze")}
        </button>
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
