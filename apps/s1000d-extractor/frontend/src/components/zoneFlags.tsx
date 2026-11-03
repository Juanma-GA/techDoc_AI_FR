import type { NodeRef } from "../lib/api";
import { Badge } from "@internal/ui";
import { useTranslation } from "react-i18next";

const ZONE_LABEL: Record<string, string> = {
  header: "migration.zoneFlags.header",
  footer: "migration.zoneFlags.footer",
  chapter: "migration.zoneFlags.chapter",
  cover: "migration.zoneFlags.cover",
  toc: "migration.zoneFlags.toc",
};

/**
 * Humanize raw machine tokens (snake_case, enum keys) to Title Case.
 * E.g., "zone_unknown_type" → "Zone Unknown Type"
 * Complies with HR21: never render raw machine tokens.
 */
function humanizeToken(token: string): string {
  return token
    .split("_")
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function ZoneFlag({ zone }: { zone?: string }) {
  const { t } = useTranslation();
  if (!zone || zone === "body") return null;
  const variant = zone === "chapter" ? "info" : "danger";
  const label = ZONE_LABEL[zone] ? t(ZONE_LABEL[zone]) : humanizeToken(zone);
  return <Badge variant={variant} title={t("migration.zoneFlags.flagHelp")}>{label}</Badge>;
}

export function ReviewFlag({ zone }: { zone?: string }) {
  const { t } = useTranslation();
  if (!zone || zone === "body" || zone === "chapter") return null;
  return (
    <Badge variant="danger" title={t("migration.zoneFlags.reviewHelp")}>
      {t("migration.zoneFlags.review")}
    </Badge>
  );
}

export function PageFlag({ page }: { page?: number | null }) {
  const { t } = useTranslation();
  if (page == null) return null;
  return <Badge>{t("common.pageShort")}{page}</Badge>;
}

export function RefFlag({ refs }: { refs?: NodeRef[] | null }) {
  const { t } = useTranslation();
  if (!refs || refs.length === 0) return null;
  return <Badge variant="info">{t("migration.zoneFlags.link")}</Badge>;
}

export function TableFlag({ kind }: { kind: string }) {
  const { t } = useTranslation();
  if (kind !== "table") return null;
  return <Badge variant="warning">{t("migration.zoneFlags.table")}</Badge>;
}
