import { useTranslation } from "react-i18next";

import type { NomenclatureMatrixState, NomenclatureMultiCompareDto } from "../../lib/api";

type Props = {
  result: NomenclatureMultiCompareDto;
  labelOf: (runId: string) => string;
};

const STATE_VARIANT: Record<NomenclatureMatrixState, "default" | "ok" | "danger" | "warn"> = {
  unchanged: "default",
  added: "ok",
  removed: "danger",
  changed: "warn",
  reference: "default",
};

export function NomenclatureMatrix({ result, labelOf }: Props) {
  const { t } = useTranslation();

  return (
    <article className="card">
      <h2 className="card-title">{t("diff.matrixTitle")}</h2>
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
                    fontFamily: '"JetBrains Mono", monospace',
                  }}
                >
                  {row.sin}
                </td>
                <td>{row.designation}</td>
                {row.cells.map((cell) => (
                  <td key={cell.run_id}>
                    <span style={{ fontFamily: '"JetBrains Mono", monospace' }}>
                      {cell.present ? cell.pn || t("diff.present") : t("diff.absent")}
                    </span>
                    {cell.state !== "unchanged" ? (
                      <>
                        <br />
                        <span className={`badge ${STATE_VARIANT[cell.state]}`}>
                          {t(`diff.matrixState.${cell.state}`)}
                        </span>
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
    </article>
  );
}
