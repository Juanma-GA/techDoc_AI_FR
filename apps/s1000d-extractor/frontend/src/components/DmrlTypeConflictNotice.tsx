import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { DmrlRow } from "../lib/wizardTypes";

export function DmrlTypeConflictNotice({ rows }: { rows: DmrlRow[] }) {
  const { t } = useTranslation();
  const pendingCount = rows.filter((row) => !row.dm_type).length;
  const [expanded, setExpanded] = useState(pendingCount > 0);

  useEffect(() => {
    setExpanded(pendingCount > 0);
  }, [pendingCount]);

  if (!rows.length) return null;

  return (
    <details
      className="banner warn"
      role={pendingCount ? "alert" : "status"}
      open={expanded}
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary className="cursor-pointer">
        <strong>{t("migration.dmrl.typeIssuesTitle", { count: rows.length })}</strong>{" "}
        {pendingCount
          ? t("migration.dmrl.typeIssuesPending", { count: pendingCount })
          : t("migration.dmrl.typeIssuesResolved")}
      </summary>
      <ul>
        {rows.map((row) => {
          const details: string[] = [];
          if (row.type_conflict) {
            details.push(t("migration.dmrl.typeConflict", {
              infoCode: row.info_code || t("common.none"),
              schema: row.info_code_schema || t("common.none"),
              mappedType: row.info_code_dm_type
                ? ` (${t(`dmType.${row.info_code_dm_type}`)})`
                : "",
              dmrlType: row.dmrl_type || t("common.none"),
            }));
          }
          if (row.type_issue === "missing_info_code") {
            details.push(t("migration.dmrl.missingInfoCode", {
              dmrlType: row.dmrl_type || t("common.none"),
            }));
          } else if (row.type_issue === "unmapped_info_code") {
            details.push(t("migration.dmrl.unmappedInfoCode", {
              infoCode: row.info_code || t("common.none"),
              dmrlType: row.dmrl_type || t("common.none"),
            }));
          } else if (row.type_issue === "unsupported_schema") {
            details.push(t("migration.dmrl.unsupportedSchema", {
              infoCode: row.info_code || t("common.none"),
              schema: row.info_code_schema || t("common.none"),
            }));
          }

          return (
            <li key={row.index}>
              <strong>
                <a
                  className="font-semibold underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  href={`#dmrl-type-${row.index}`}
                >
                  {row.title || row.dmc || t("common.none")}
                </a>
              </strong>: {details.join(" ")}{" "}
              {row.dm_type
                ? t("migration.dmrl.typeSelected", {
                    type: t(`dmType.${row.dm_type}`),
                  })
                : t("migration.dmrl.typeResolutionRequiredRow")}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
