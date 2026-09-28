import { useTranslation } from "react-i18next";

import { exportUrl, type NomenclatureCompareDto } from "../../lib/api";

type Props = {
  result: NomenclatureCompareDto;
  pairLabel?: string;
};

type Entry = NomenclatureCompareDto["added_sin"][number];

function ResultTable({ title, entries, prefix }: { title: string; entries: Entry[]; prefix: string }) {
  const { t } = useTranslation();
  return (
    <>
      <h3 className="label" style={{ marginTop: 12 }}>{title}</h3>
      <table className="tbl">
        <thead>
          <tr>
            <th>{t("diff.colSin")}</th>
            <th>{t("diff.colOldPn")}</th>
            <th>{t("diff.colOldPnV2")}</th>
            <th>{t("diff.colDesignation")}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={`${prefix}-${entry.sin}`}>
              <td>{entry.sin}</td>
              <td>{entry.old_pn}</td>
              <td>{entry.old_pn_v2}</td>
              <td>{entry.designation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export function NomenclatureComparisonResult({ result, pairLabel }: Props) {
  const { t } = useTranslation();
  return (
    <article className="card">
      <div className="row" style={{ marginBottom: 8 }}>
        <div>
          <h2 className="card-title" style={{ margin: 0 }}>{t("diff.resultTitle")}</h2>
          {pairLabel ? <p className="hint" style={{ margin: "0.25rem 0 0" }}>{pairLabel}</p> : null}
        </div>
        <a
          href={exportUrl.nomenclatureCompareCsv(result.base_run_id, result.other_run_id)}
          style={{ marginLeft: "auto" }}
        >
          <button type="button" className="btn secondary small">{t("diff.exportCsv")}</button>
        </a>
      </div>
      <p className="hint">
        {t("diff.nomenSummary", {
          added: result.summary.added ?? 0,
          removed: result.summary.removed ?? 0,
          changed: result.summary.changed ?? 0,
        })}
      </p>
      <ResultTable title={t("diff.sinAdded")} entries={result.added_sin} prefix="a" />
      <ResultTable title={t("diff.sinRemoved")} entries={result.removed_sin} prefix="r" />
      <ResultTable title={t("diff.pnChanged")} entries={result.changed_pn} prefix="c" />
    </article>
  );
}
