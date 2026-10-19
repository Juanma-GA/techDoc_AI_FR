import { useTranslation } from "react-i18next";

import { exportUrl, type NomenclatureCompareDto } from "../../lib/api";

type Props = {
  result: NomenclatureCompareDto;
  pairLabel?: string;
};

type Entry = NomenclatureCompareDto["added_sin"][number];

export function NomenclatureComparisonResult({ result, pairLabel }: Props) {
  const { t } = useTranslation();
  const sections: { key: string; title: string; entries: Entry[] }[] = [
    { key: "added", title: t("diff.sinAdded"), entries: result.added_sin },
    { key: "removed", title: t("diff.sinRemoved"), entries: result.removed_sin },
    { key: "changed", title: t("diff.pnChanged"), entries: result.changed_pn },
  ];

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
      <div style={{ overflowX: "auto" }}>
        <table className="tbl">
          <colgroup>
            <col style={{ width: "16%" }} />
            <col style={{ width: "25%" }} />
            <col style={{ width: "25%" }} />
            <col style={{ width: "34%" }} />
          </colgroup>
          <thead>
            <tr>
              <th>{t("diff.colSin")}</th>
              <th style={{ textTransform: "none" }}>{t("diff.colOldPn")}</th>
              <th style={{ textTransform: "none" }}>{t("diff.colOldPnV2")}</th>
              <th>{t("diff.colDesignation")}</th>
            </tr>
          </thead>
          {sections.map((section) => (
            <tbody key={section.key}>
              <tr>
                <th
                  colSpan={4}
                  scope="rowgroup"
                  className="label"
                  style={{ textAlign: "left", background: "var(--bg-2)" }}
                >
                  {section.title}
                </th>
              </tr>
              {section.entries.map((entry) => (
                <tr key={`${section.key}-${entry.sin}`}>
                  <td>{entry.sin}</td>
                  <td>{entry.old_pn}</td>
                  <td>{entry.old_pn_v2}</td>
                  <td>{entry.designation}</td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </article>
  );
}
