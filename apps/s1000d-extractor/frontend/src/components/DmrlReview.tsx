import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { DmrlRow } from "../lib/api";
import { DmrlTypeConflictNotice } from "./DmrlTypeConflictNotice";

export const DM_TYPES = ["descriptive", "procedural", "ipd"] as const;

type DmrlReviewProps = {
  rows: DmrlRow[];
  dmCount: number;
  busy: boolean;
  edits: Record<number, string>;
  onTitleChange: (index: number, title: string) => void;
  onUpdate: (params: Record<string, unknown>) => void;
  onAdvance: () => void;
};

function MatchBadge({ row }: { row: DmrlRow }) {
  const { t } = useTranslation();
  if (!row.matched) return <span className="badge warn">{t("migration.match.notFound")}</span>;
  const page = row.page ?? "?";
  if (row.match_rank === "exact")
    return <span className="badge ok">{t("migration.match.exact", { page })}</span>;
  return (
    <span className="badge warn" title={row.matched_text}>
      {t(`migration.match.${row.match_rank || "contains"}`, { page })}
    </span>
  );
}

function needsExplicitTypeChoice(row: DmrlRow): boolean {
  return Boolean((row.type_conflict || row.type_issue) && !row.dm_type);
}

function ConfirmExcludeButton({
  busy,
  label,
  confirmLabel,
  onConfirm,
}: {
  busy: boolean;
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return (
    <button
      type="button"
      className="btn danger small"
      disabled={busy}
      onClick={() => {
        if (!armed) {
          setArmed(true);
          timer.current = setTimeout(() => {
            setArmed(false);
            timer.current = null;
          }, 3000);
          return;
        }
        if (timer.current) clearTimeout(timer.current);
        timer.current = null;
        setArmed(false);
        onConfirm();
      }}
    >
      {armed ? confirmLabel : label}
    </button>
  );
}

export function DmrlReview({
  rows,
  dmCount,
  busy,
  edits,
  onTitleChange,
  onUpdate,
  onAdvance,
}: DmrlReviewProps) {
  const { t } = useTranslation();
  const dmRows = rows.filter((row) => !row.is_pm_title);
  const missingRows = dmRows.filter((row) => !row.matched);
  const missingCount = missingRows.length;
  const uncertainCount = dmRows.filter(
    (row) => row.matched && row.match_rank !== "exact",
  ).length;
  const pmTitleCount = rows.length - dmRows.length;
  const typeReviewRows = dmRows.filter((row) => row.type_conflict || row.type_issue);
  const unresolvedTypeCount = typeReviewRows.filter((row) => !row.dm_type).length;

  return (
    <div className="card">
      <h2 className="card-title">
        {t("migration.dmrl.title", { count: dmCount })}
      </h2>
      <p className="label">
        {t("migration.dmrl.help")}{" "}
        {t("migration.dmrl.counts", {
          missing: missingCount,
          uncertain: uncertainCount,
          pmTitles: pmTitleCount,
        })}
      </p>
      {missingCount > 0 ? (
        <div className="banner warn" role="status">
          <p>
            <strong>{t("migration.dmrl.missingAlert", { count: missingCount })}</strong>{" "}
            {t("migration.dmrl.missingAlertHelp", { count: missingCount })}
          </p>
          {missingRows.map((row) => (
            <div className="row" key={row.index}>
              <span className="grow">
                <strong>{row.title || row.dmc || t("common.none")}</strong>{" "}
                {row.title && row.dmc ? <span className="label">{row.dmc}</span> : null}
              </span>
              <ConfirmExcludeButton
                busy={busy}
                label={t("migration.dmrl.exclude")}
                confirmLabel={t("migration.dmrl.confirmExclude")}
                onConfirm={() => onUpdate({ op: "exclude", index: row.index })}
              />
            </div>
          ))}
        </div>
      ) : null}
      <DmrlTypeConflictNotice rows={typeReviewRows} />
      <div className="row" style={{ marginBottom: 10 }}>
        <button
          type="button"
          className="btn primary"
          style={{ marginLeft: "auto" }}
          disabled={busy || unresolvedTypeCount > 0}
          onClick={onAdvance}
        >
          {t("migration.dmrl.validate")}
        </button>
      </div>
      <div>
        {rows.map((row) => (
          <div
            key={row.index}
            className="row"
            style={{ borderBottom: "1px solid var(--border)", padding: "6px 0" }}
          >
            <span className="badge info">{row.arbo || t("common.none")}</span>
            <input
              className="input grow"
              aria-label={t("migration.dmrl.titleInput", { title: row.title })}
              value={edits[row.index] ?? row.title}
              onChange={(event) => onTitleChange(row.index, event.target.value)}
            />
            {row.is_pm_title ? (
              <span className="badge info">{t("migration.dmrl.pmTitle")}</span>
            ) : (
              <>
                <select
                  id={`dmrl-type-${row.index}`}
                  aria-label={t("migration.dmrl.typeLabel", { title: row.title })}
                  aria-invalid={needsExplicitTypeChoice(row)}
                  disabled={busy}
                  value={needsExplicitTypeChoice(row) ? "" : row.dm_type || "descriptive"}
                  onChange={(event) =>
                    onUpdate({
                      op: "set_type",
                      index: row.index,
                      dm_type: event.target.value,
                    })
                  }
                >
                  {needsExplicitTypeChoice(row) ? (
                    <option value="">{t("migration.dmrl.selectType")}</option>
                  ) : null}
                  {DM_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`dmType.${type}`)}
                    </option>
                  ))}
                </select>
                <MatchBadge row={row} />
                <span className="label" title={row.dmc}>
                  {row.dmc || t("common.none")}
                </span>
                <span
                  className="label"
                  title={row.icn || undefined}
                  style={{ maxWidth: 280, whiteSpace: "pre-line", overflowWrap: "anywhere" }}
                >
                  <strong>{t("migration.dmrl.icn")}:</strong>{" "}
                  {row.icn || t("common.none")}
                </span>
              </>
            )}
            <button
              type="button"
              className="btn ghost small"
              disabled={busy || unresolvedTypeCount > 0}
              onClick={() =>
                onUpdate({
                  op: "rename",
                  index: row.index,
                  title: edits[row.index] ?? row.title,
                })
              }
            >
              {t("migration.dmrl.rename")}
            </button>
          </div>
        ))}
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button
          type="button"
          className="btn primary"
          style={{ marginLeft: "auto" }}
          disabled={busy}
          onClick={onAdvance}
        >
          {t("migration.dmrl.validate")}
        </button>
      </div>
    </div>
  );
}
