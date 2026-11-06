import { Badge, Button, Select, Spinner } from "@internal/ui";
import { ArrowDown, ArrowUp, GitCompareArrows, X } from "lucide-react";
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
            <Select options={[]}  value={id} onChange={(event) => onReplace(index, event.target.value)}>
              {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </label>
        ))}
        <Button type="button" variant="primary" onClick={onCompare} disabled={pending}>
          {pending ? <Spinner aria-label={t("common.loading")} /> : <GitCompareArrows size={16} aria-hidden="true" />}
          {t("diff.compare")}
        </Button>
      </div>
    );
  }

  return (
    <>
      <div className="grid-2">
        <label className="field">
          <span className="field-label">{t("diff.multiMode")}</span>
          <Select options={[]}

            value={mode}
            onChange={(event) => onModeChange(event.target.value as NomenclatureCompareMode)}
          >
            <option value="chronology">{t("diff.modeChronology")}</option>
            <option value="reference">{t("diff.modeReference")}</option>
          </Select>
        </label>
        {mode === "reference" ? (
          <label className="field">
            <span className="field-label">{t("diff.referenceVersion")}</span>
            <Select options={[]}  value={referenceId} onChange={(event) => onReferenceChange(event.target.value)}>
              {selected.map((id) => (
                <option key={id} value={id}>{options.find((option) => option.value === id)?.label ?? id}</option>
              ))}
            </Select>
          </label>
        ) : null}
      </div>
      <div className="form" style={{ marginTop: "0.75rem" }}>
        {selected.map((id, index) => (
          <div className="row" key={id}>
            <Badge variant="default">{`V${index}`}</Badge>
            <Select options={[]} className="grow" aria-label={t("common.version", { index })} value={id} onChange={(event) => onReplace(index, event.target.value)}>
              {options
                .filter((option) => option.value === id || !selected.includes(option.value))
                .map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
            <Button type="button" variant="ghost" size="icon" title={t("diff.moveUp")} aria-label={t("diff.moveUp")} onClick={() => onMove(index, -1)} disabled={index === 0}>
              <ArrowUp size={16} aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="ghost" size="icon"
              title={t("diff.moveDown")}
              aria-label={t("diff.moveDown")}
              onClick={() => onMove(index, 1)}
              disabled={index === selected.length - 1}
            >
              <ArrowDown size={16} aria-hidden="true" />
            </Button>
            <Button type="button" variant="ghost" size="icon" title={t("diff.removeVersion")} aria-label={t("diff.removeVersion")} onClick={() => onRemove(index)}>
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="primary"
        style={{ marginTop: "0.75rem" }}
        onClick={onCompare}
        disabled={pending || selected.length > maxVersions}
      >
        {pending ? <Spinner aria-label={t("common.loading")} /> : <GitCompareArrows size={16} aria-hidden="true" />}
        {t("diff.compareVersions", { count: selected.length })}
      </Button>
    </>
  );
}
