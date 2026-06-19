import { Trash2 } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { Badge, type BadgeProps, Spinner } from "@internal/ui";

import { PageHeader } from "../components/PageHeader";
import { PdfUploadZone } from "../components/upload/PdfUploadZone";
import { StandardPicker } from "../components/upload/StandardPicker";
import { useDeleteDocument, useDocuments, useUploadDocument } from "../hooks/useDocuments";
import { useStandards } from "../hooks/useStandards";
import { useFiltersStore } from "../stores/filtersStore";
import type { Document } from "../types/domain";

type TargetUnit = "metric" | "imperial" | "auto";

const TARGET_UNITS: TargetUnit[] = ["auto", "metric", "imperial"];

const STATUS_VARIANT: Record<string, NonNullable<BadgeProps["variant"]>> = {
  uploaded: "info",
  analyzing: "warning",
  analyzed: "success",
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
  const targetUnit = useFiltersStore((s) => s.targetUnit);
  const setTargetUnit = useFiltersStore((s) => s.setTargetUnit);
  const lastStandardId = useFiltersStore((s) => s.lastStandardId);
  const lastStandardVersionId = useFiltersStore((s) => s.lastStandardVersionId);
  const setLastStandard = useFiltersStore((s) => s.setLastStandard);

  // Active target-standard label for the banner (preview lines 289-293).
  // React's filtersStore is single-valued (the Settings multi-select is a
  // separate, flagged store change); we surface that single active standard.
  const activeStandardLabel = useMemo(() => {
    const items = standards.data ?? [];
    const std = items.find((s) => s.id === lastStandardId);
    if (!std) return null;
    const version = std.versions.find((v) => v.id === lastStandardVersionId);
    return version ? `${std.code} ${version.label}` : std.code;
  }, [standards.data, lastStandardId, lastStandardVersionId]);

  const handleUpload = (file: File): void => {
    upload.mutate(
      { file, target: targetUnit, standardVersionId: lastStandardVersionId },
      {
        onSuccess: (doc: Document) => navigate(`/documents/${doc.id}`),
      },
    );
  };

  return (
    <div>
      <PageHeader title={t("documents.title")} subtitle={t("documents.subtitle")} />

      <section className="card">
        {/* Active target-standard banner (preview 289-293) */}
        <div className="banner">
          <span>{t("documents.activeStandardLabel")}</span>
          <strong className="label">{activeStandardLabel ?? "—"}</strong>
          <Link to="/settings" className="grow" style={{ textAlign: "right" }}>
            {t("documents.changeStandard")}
          </Link>
        </div>

        <div className="form">
          {/* Per-upload target-unit slicer, synced with Settings (preview 295-300) */}
          <div className="field">
            <span className="field-label">{t("documents.targetUnit")}</span>
            <div className="row">
              {TARGET_UNITS.map((unit) => (
                <button
                  key={unit}
                  type="button"
                  aria-pressed={targetUnit === unit}
                  onClick={() => setTargetUnit(unit)}
                  className={["btn small", targetUnit === unit ? "primary" : "ghost"].join(" ")}
                >
                  {t(`settings.targetUnit.${unit}`)}
                </button>
              ))}
            </div>
          </div>

          <StandardPicker
            standardId={lastStandardId}
            versionId={lastStandardVersionId}
            onChange={setLastStandard}
          />
          <PdfUploadZone onFile={handleUpload} disabled={upload.isPending} />
        </div>

        {docs.isLoading ? (
          <p className="empty-state">{t("common.loading")}</p>
        ) : docs.data && docs.data.length > 0 ? (
          <ul className="grid-2">
            {docs.data.map((doc) => {
              const variant = STATUS_VARIANT[doc.status] ?? "info";
              return (
                <li key={doc.id} className="card">
                  <div className="row">
                    <h3 className="card-title label grow">{doc.original_filename}</h3>
                    <Badge variant={variant}>
                      {doc.status === "analyzing" ? <Spinner size="sm" /> : null}
                      {t(`status.${doc.status}`)}
                    </Badge>
                  </div>
                  <p className="card-sub label">
                    {doc.page_count} pages · v{doc.current_version} · {doc.target_unit_system}
                  </p>
                  <div className="item-actions" style={{ marginTop: "0.5rem" }}>
                    <button
                      type="button"
                      onClick={() => navigate(`/documents/${doc.id}`)}
                      className="btn small primary"
                    >
                      {t("documents.open")}
                    </button>
                    <button
                      type="button"
                      aria-label={t("documents.delete")}
                      onClick={() => remove.mutate(doc.id)}
                      className="btn small danger"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="empty-state">{t("documents.empty")}</p>
        )}
      </section>
    </div>
  );
}
