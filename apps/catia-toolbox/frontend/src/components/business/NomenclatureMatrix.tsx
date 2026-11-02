import { Badge, type BadgeProps } from "@internal/ui";
import { useTranslation } from "react-i18next";

import type { NomenclatureMatrixState, NomenclatureMultiCompareDto } from "../../lib/api";

type Props = {
  result: NomenclatureMultiCompareDto;
  labelOf: (runId: string) => string;
};

const STATE_VARIANT: Record<NomenclatureMatrixState, BadgeProps["variant"]> = {
  unchanged: "default",
  added: "success",
  removed: "danger",
  changed: "warning",
  reference: "default",
};

export function NomenclatureMatrix({ result, labelOf }: Props) {
  const { t } = useTranslation();

  return (
    <section className="workflow-section">
      <h2 className="section-title">{t("diff.matrixTitle")}</h2>
      <p className="hint">{t("diff.matrixHint")}</p>
      <div style={{ overflowX: "auto" }}>
        <table className="tbl" style={{ minWidth: `${28 + result.run_ids.length * 14}rem` }}>
          <thead>
            <tr>
              <th style={{ position: "sticky", left: 0, background: "var(--bg-2)", zIndex: 1 }}>
                {t("diff.colSin")}
              </th>
              <th>{t("diff.colDesignation")}</th>
              {result.run_ids.map((runId, index) => (
                <th key={runId}>
                  <span className="label">{`V${index}`}</span>
                  <br />
                  <span>{labelOf(runId)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.matrix.map((row) => (
              <tr key={row.sin}>
                <td
                  style={{
                    position: "sticky",
                    left: 0,
                    background: "var(--bg-2)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {row.sin}
                </td>
                <td>{row.designation}</td>
                {row.cells.map((cell) => (
                  <td key={cell.run_id}>
                    <span style={{ fontFamily: "var(--font-mono)" }}>
                      {cell.present ? cell.pn || t("diff.present") : t("diff.absent")}
                    </span>
                    {cell.state !== "unchanged" ? (
                      <>
                        <br />
                        <Badge variant={STATE_VARIANT[cell.state]}>
                          {t(`diff.matrixState.${cell.state}`)}
                        </Badge>
                      </>
                    ) : null}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.matrix.length === 0 ? <p className="hint">{t("diff.noDifference")}</p> : null}
    </section>
  );
}
