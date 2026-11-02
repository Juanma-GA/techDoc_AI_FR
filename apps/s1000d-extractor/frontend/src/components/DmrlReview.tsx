import { useTranslation } from "react-i18next";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  SelectMenu,
} from "@internal/ui";
import { ConfirmButton } from "./ConfirmButton";
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
  if (!row.matched) return <Badge variant="warning">{t("migration.match.notFound")}</Badge>;
  if (row.match_rank === "exact")
    return <Badge variant="success" className="whitespace-nowrap">
      {t("migration.match.exact", { page: row.page ?? "?" })}
    </Badge>;
  return (
    <Badge variant="warning" title={row.matched_text} className="whitespace-nowrap">
      {t(`migration.match.${row.match_rank || "contains"}`)}
    </Badge>
  );
}

function needsExplicitTypeChoice(row: DmrlRow): boolean {
  return Boolean((row.type_conflict || row.type_issue) && !row.dm_type);
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
    <Card>
      <CardHeader><CardTitle>{t("migration.dmrl.title", { count: dmCount })}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
      <p className="text-sm text-fg-dim">
        {t("migration.dmrl.help")}{" "}
        {t("migration.dmrl.counts", {
          missing: missingCount,
          uncertain: uncertainCount,
          pmTitles: pmTitleCount,
        })}
      </p>
      {missingCount > 0 ? (
        <Alert variant="warning">
          <p>
            <strong>{t("migration.dmrl.missingAlert", { count: missingCount })}</strong>{" "}
            {t("migration.dmrl.missingAlertHelp", { count: missingCount })}
          </p>
          {missingRows.map((row) => (
            <div className="flex flex-wrap items-center gap-3" key={row.index}>
              <span className="min-w-0 flex-1">
                <strong>{row.title || row.dmc || t("common.none")}</strong>{" "}
                {row.title && row.dmc ? (
                  <span className="text-label font-mono uppercase text-fg-dim">{row.dmc}</span>
                ) : null}
              </span>
              <ConfirmButton
                size="sm"
                disabled={busy}
                label={t("migration.dmrl.exclude")}
                confirmLabel={t("migration.dmrl.confirmExclude")}
                onConfirm={() => onUpdate({ op: "exclude", index: row.index })}
              />
            </div>
          ))}
        </Alert>
      ) : null}
      <DmrlTypeConflictNotice rows={typeReviewRows} />
      <div className="flex justify-end">
        <Button
          type="button"
          disabled={busy || unresolvedTypeCount > 0}
          onClick={onAdvance}
        >
          {t("migration.dmrl.validate")}
        </Button>
      </div>
      <div className="s1k-dmrl-rows">
        {rows.map((row) => (
          <div key={row.index} className="s1k-dmrl-row border-b border-md py-1.5">
            <Badge variant="info" className="justify-self-start">{row.arbo || t("common.none")}</Badge>
            <Input
              className="min-w-0 w-full"
              aria-label={t("migration.dmrl.titleInput", { title: row.title })}
              value={edits[row.index] ?? row.title}
              onChange={(event) => onTitleChange(row.index, event.target.value)}
            />
            {row.is_pm_title ? (
              <Badge variant="info">{t("migration.dmrl.pmTitle")}</Badge>
            ) : (
              <>
                <SelectMenu
                  triggerClassName="s1k-dm-type-select w-full"
                  id={`dmrl-type-${row.index}`}
                  label={t("migration.dmrl.typeLabel", { title: row.title })}
                  disabled={busy}
                  value={needsExplicitTypeChoice(row) ? "" : row.dm_type || "descriptive"}
                  state={needsExplicitTypeChoice(row) ? "error" : "default"}
                  options={[
                    ...(needsExplicitTypeChoice(row)
                      ? [{ value: "", label: t("migration.dmrl.selectType") }]
                      : []),
                    ...DM_TYPES.map((type) => ({ value: type, label: t(`dmType.${type}`) })),
                  ]}
                  onValueChange={(dm_type) => onUpdate({
                      op: "set_type",
                      index: row.index,
                      dm_type,
                    })}
                />
                <MatchBadge row={row} />
                <span className="min-w-0 break-all text-label font-mono uppercase text-fg-dim" title={row.dmc}>
                  {row.dmc || t("common.none")}
                </span>
                <span
                  className="min-w-0 whitespace-pre-line break-words text-label font-mono uppercase text-fg-dim"
                  title={row.icn || undefined}
                >
                  <strong>{t("migration.dmrl.icn")}:</strong>{" "}
                  {row.icn || t("common.none")}
                </span>
              </>
            )}
            {row.is_pm_title ? <span aria-hidden="true" /> : null}
            {row.is_pm_title ? <span aria-hidden="true" /> : null}
            {row.is_pm_title ? <span aria-hidden="true" /> : null}
            <Button
              type="button"
              variant="ghost"
              size="sm"
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
            </Button>
          </div>
        ))}
      </div>
      <div className="flex justify-end pt-3">
        <Button
          type="button"
          disabled={busy}
          onClick={onAdvance}
        >
          {t("migration.dmrl.validate")}
        </Button>
      </div>
      </CardContent>
    </Card>
  );
}
