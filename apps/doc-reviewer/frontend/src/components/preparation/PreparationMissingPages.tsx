import { useState } from "react";
import { useTranslation } from "react-i18next";

type Props = {
  groups: string[][];
  absentGroups?: string[][];
  pageCount: number;
  saving: boolean;
  onProvide: (page: number, pageType: string) => void;
  onAbsent: (pageTypes: string[], absent: boolean) => void;
};

function MissingPageType({
  group,
  pageCount,
  saving,
  onProvide,
  onAbsent,
}: {
  group: string[];
  pageCount: number;
  saving: boolean;
  onProvide: Props["onProvide"];
  onAbsent: Props["onAbsent"];
}) {
  const { t } = useTranslation();
  const key = group.join("-");
  const [pageType, setPageType] = useState(group[0] ?? "");
  const [page, setPage] = useState("");
  const pageNumber = Number(page);
  const valid = Number.isInteger(pageNumber) && pageNumber >= 1 && pageNumber <= pageCount;

  return (
    <li className="prep-missing-item">
      <strong className="prep-missing-type">{group.join(" / ")}</strong>
      <div className="prep-missing-fields">
        {group.length > 1 ? (
          <label className="prep-missing-type-control">
            <span>{t("preparation.pageType")}</span>
            <select
              className="input small"
              value={pageType}
              disabled={saving}
              onChange={(event) => setPageType(event.target.value)}
            >
              {group.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="prep-missing-type-spacer" aria-hidden="true" />
        )}
        <label className="prep-missing-page-control" htmlFor={`missing-page-${key}`}>
          <span>{t("preparationUi.missing.pageLabel", { count: pageCount })}</span>
          <input
            id={`missing-page-${key}`}
            className="input small"
            type="number"
            min={1}
            max={pageCount}
            value={page}
            disabled={saving}
            onChange={(event) => setPage(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="btn secondary small"
          disabled={saving || !valid}
          onClick={() => onProvide(pageNumber, pageType)}
        >
          {t("preparationUi.missing.provide")}
        </button>
        <button
          type="button"
          className="btn ghost small"
          disabled={saving}
          onClick={() => onAbsent(group, true)}
        >
          {t("preparationUi.missing.notPresent")}
        </button>
      </div>
    </li>
  );
}

export function PreparationMissingPages({
  groups,
  absentGroups = [],
  pageCount,
  saving,
  onProvide,
  onAbsent,
}: Props) {
  const { t } = useTranslation();
  if (groups.length === 0 && absentGroups.length === 0) return null;
  return (
    <section className="prep-missing" role="status">
      <h3 className="prep-missing-title">{t("preparationUi.missing.title")}</h3>
      <p className="hint">{t("preparationUi.missing.hint")}</p>
      <ul className="prep-missing-list">
        {groups.map((group) => (
          <MissingPageType
            key={group.join("-")}
            group={group}
            pageCount={pageCount}
            saving={saving}
            onProvide={onProvide}
            onAbsent={onAbsent}
          />
        ))}
        {absentGroups.map((group) => (
          <li key={`absent-${group.join("-")}`} className="prep-missing-item">
            <strong className="prep-missing-type">{group.join(" / ")}</strong>
            <div className="prep-missing-fields prep-missing-fields--absent">
              <span className="prep-type-meta">{t("preparationUi.missing.markedAbsent")}</span>
              <button
                type="button"
                className="btn ghost small"
                disabled={saving}
                onClick={() => onAbsent(group, false)}
              >
                {t("preparationUi.missing.undo")}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
