import { useTranslation } from "react-i18next";

import type { NomenclatureCompareMode } from "../../lib/api";

export type NomenclatureOption = { value: string; label: string };

type Props = {
  options: NomenclatureOption[];
  selected: string[];
  mode: NomenclatureCompareMode;
  referenceId: string;
  pending: boolean;
  maxVersions: number;
  onReplace: (index: number, value: string) => void;
  onMove: (index: number, offset: number) => void;
  onRemove: (index: number) => void;
  onModeChange: (mode: NomenclatureCompareMode) => void;
  onReferenceChange: (id: string) => void;
  onCompare: () => void;
};

export function NomenclatureVersionSelector({
  options,
  selected,
  mode,
  referenceId,
  pending,
  maxVersions,
  onReplace,
  onMove,
  onRemove,
  onModeChange,
  onReferenceChange,
  onCompare,
}: Props) {
  const { t } = useTranslation();

  if (selected.length === 2) {
    return (
      <div className="row" style={{ alignItems: "flex-end" }}>
        {selected.map((id, index) => (
          <label className="field grow" key={index}>
            <span className="field-label">{t(index === 0 ? "diff.nomenBase" : "diff.nomenOther")}</span>
            <select className="input" value={id} onChange={(event) => onReplace(index, event.target.value)}>
              {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        ))}
        <button type="button" className="btn primary" onClick={onCompare} disabled={pending}>
          {t("diff.compare")}
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="grid-2">
        <label className="field">
          <span className="field-label">{t("diff.multiMode")}</span>
          <select
            className="input"
            value={mode}
            onChange={(event) => onModeChange(event.target.value as NomenclatureCompareMode)}
          >
            <option value="chronology">{t("diff.modeChronology")}</option>
            <option value="reference">{t("diff.modeReference")}</option>
          </select>
        </label>
        {mode === "reference" ? (
          <label className="field">
            <span className="field-label">{t("diff.referenceVersion")}</span>
            <select className="input" value={referenceId} onChange={(event) => onReferenceChange(event.target.value)}>
              {selected.map((id) => (
                <option key={id} value={id}>{options.find((option) => option.value === id)?.label ?? id}</option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      <div className="form" style={{ marginTop: "0.75rem" }}>
        {selected.map((id, index) => (
          <div className="row" key={id}>
            <span className="badge default">{`V${index}`}</span>
            <select className="input grow" value={id} onChange={(event) => onReplace(index, event.target.value)}>
              {options
                .filter((option) => option.value === id || !selected.includes(option.value))
                .map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <button type="button" className="btn ghost small" onClick={() => onMove(index, -1)} disabled={index === 0}>
              {t("diff.moveUp")}
            </button>
            <button
              type="button"
              className="btn ghost small"
              onClick={() => onMove(index, 1)}
              disabled={index === selected.length - 1}
            >
              {t("diff.moveDown")}
            </button>
            <button type="button" className="btn ghost small" onClick={() => onRemove(index)}>
              {t("diff.removeVersion")}
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="btn primary"
        style={{ marginTop: "0.75rem" }}
        onClick={onCompare}
        disabled={pending || selected.length > maxVersions}
      >
        {t("diff.compareVersions", { count: selected.length })}
      </button>
    </>
  );
}
