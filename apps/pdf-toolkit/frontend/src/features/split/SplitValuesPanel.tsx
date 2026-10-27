import { useId, useState } from "react";
import { ListPlus, ScanText, Table2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Input, Select, Spinner, Textarea } from "@internal/ui";
import {
  chunkRows,
  clampZone,
  parsePastedRows,
  type GroupingMode,
  type MissingValueMode,
  type SearchScope,
  type SplitRow,
  type SplitZone,
  type ValueType,
} from "./splitModel";

export type SplitMode = "table" | "zone";

export type ZoneSettings = {
  scope: SearchScope;
  zone: SplitZone;
  valueType: ValueType;
  customPattern: string;
  grouping: GroupingMode;
  missing: MissingValueMode;
};

type SplitValuesPanelProps = {
  mode: SplitMode;
  settings: ZoneSettings;
  pageCount: number;
  disabled: boolean;
  detecting: boolean;
  progress: { completed: number; total: number };
  patternError: boolean;
  onModeChange: (mode: SplitMode) => void;
  onSettingsChange: (settings: ZoneSettings) => void;
  onDetect: () => void;
  onAppendRows: (rows: SplitRow[]) => void;
  onReplaceRows: (rows: SplitRow[]) => void;
};

const zoneFields = ["x", "y", "width", "height"] as const;

export function SplitValuesPanel({
  mode,
  settings,
  pageCount,
  disabled,
  detecting,
  progress,
  patternError,
  onModeChange,
  onSettingsChange,
  onDetect,
  onAppendRows,
  onReplaceRows,
}: SplitValuesPanelProps) {
  const { t } = useTranslation();
  const baseId = useId();
  const [pasted, setPasted] = useState("");
  const [rejected, setRejected] = useState<number[]>([]);
  const [chunkSize, setChunkSize] = useState("1");

  const update = (patch: Partial<ZoneSettings>) => onSettingsChange({ ...settings, ...patch });

  return (
    <div className="split-values">
      <div className="split-settings">
        <label className="field-label" htmlFor={`${baseId}-chunk`}>
          {t("split.chunkLabel")}
        </label>
        <div className="split-inline-actions">
          <Input
            id={`${baseId}-chunk`}
            className="split-chunk-input"
            type="number"
            min={1}
            max={Math.max(1, pageCount)}
            value={chunkSize}
            disabled={disabled || pageCount < 1}
            onChange={(event) => setChunkSize(event.currentTarget.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={disabled || pageCount < 1 || !(Number(chunkSize) >= 1)}
            onClick={() => onReplaceRows(chunkRows(pageCount, Number(chunkSize)))}
          >
            {t("split.chunkAction")}
          </Button>
        </div>
        <p className="input-help">{t("split.chunkHelp")}</p>
      </div>

      <div className="split-mode-switch" role="group" aria-label={t("split.modeLabel")}>
        <Button
          size="sm"
          variant={mode === "table" ? "primary" : "secondary"}
          aria-pressed={mode === "table"}
          disabled={disabled}
          onClick={() => onModeChange("table")}
        >
          <Table2 size={15} aria-hidden="true" />
          {t("split.modeTable")}
        </Button>
        <Button
          size="sm"
          variant={mode === "zone" ? "primary" : "secondary"}
          aria-pressed={mode === "zone"}
          disabled={disabled}
          onClick={() => onModeChange("zone")}
        >
          <ScanText size={15} aria-hidden="true" />
          {t("split.modeZone")}
        </Button>
      </div>

      {mode === "table" ? (
        <div className="split-settings">
          <label className="field-label" htmlFor={`${baseId}-paste`}>
            {t("split.pasteLabel")}
          </label>
          <Textarea
            id={`${baseId}-paste`}
            className="page-range-input"
            rows={4}
            value={pasted}
            disabled={disabled}
            placeholder={"1-3;A320-001\n4-6;A320-002"}
            onChange={(event) => setPasted(event.currentTarget.value)}
          />
          <p className="input-help">{t("split.pasteHelp")}</p>
          <div className="split-inline-actions">
            <Button
              size="sm"
              variant="secondary"
              disabled={disabled || !pasted.trim()}
              onClick={() => {
                const result = parsePastedRows(pasted);
                setRejected(result.rejected);
                if (result.rows.length > 0) {
                  onAppendRows(result.rows);
                  if (result.rejected.length === 0) setPasted("");
                }
              }}
            >
              <ListPlus size={15} aria-hidden="true" />
              {t("split.pasteAction")}
            </Button>
          </div>
          {rejected.length > 0 ? (
            <p className="warning-note" role="alert">
              {t("split.pasteRejected", { lines: rejected.join(", ") })}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="split-settings">
          <label className="field-label" htmlFor={`${baseId}-scope`}>
            {t("split.scopeLabel")}
          </label>
          <Select
            id={`${baseId}-scope`}
            value={settings.scope}
            disabled={disabled}
            options={(["zone", "page"] as const).map((value) => ({
              value,
              label: t(`split.scope_${value}`),
            }))}
            onChange={(event) => update({ scope: event.currentTarget.value as SearchScope })}
          />
          {settings.scope === "page" ? (
            <p className="input-help">{t("split.scopePageHelp")}</p>
          ) : (
            <>
              <span className="field-label">{t("split.zoneLabel")}</span>
              <p className="input-help split-zone-help">{t("split.zoneHelp")}</p>
              <div className="split-zone-grid">
                {zoneFields.map((field) => (
                  <label key={field}>
                    <span>{t(`split.zone_${field}`)}</span>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      step="any"
                      value={Math.round(settings.zone[field] * 1000) / 10}
                      disabled={disabled}
                      onChange={(event) => {
                        const value = Number(event.currentTarget.value) / 100;
                        update({ zone: clampZone({ ...settings.zone, [field]: value }) });
                      }}
                    />
                  </label>
                ))}
              </div>
            </>
          )}
          <label className="field-label" htmlFor={`${baseId}-type`}>
            {t("split.valueTypeLabel")}
          </label>
          <Select
            id={`${baseId}-type`}
            value={settings.valueType}
            disabled={disabled}
            options={(["text", "number", "code", "regex"] as const).map((value) => ({
              value,
              label: t(`split.valueType_${value}`),
            }))}
            onChange={(event) => update({ valueType: event.currentTarget.value as ValueType })}
          />
          {settings.valueType === "regex" ? (
            <>
              <Input
                className="page-range-input split-regex-input"
                value={settings.customPattern}
                disabled={disabled}
                placeholder={"DMC-[A-Z0-9-]+"}
                aria-label={t("split.regexLabel")}
                aria-invalid={patternError}
                state={patternError ? "error" : "default"}
                onChange={(event) => update({ customPattern: event.currentTarget.value })}
              />
              <p className={patternError ? "warning-note" : "input-help"}>
                {patternError ? t("split.regexInvalid") : t("split.regexHelp")}
              </p>
            </>
          ) : null}

          <label className="field-label" htmlFor={`${baseId}-grouping`}>
            {t("split.groupingLabel")}
          </label>
          <Select
            id={`${baseId}-grouping`}
            value={settings.grouping}
            disabled={disabled}
            options={[
              { value: "change", label: t("split.grouping_change") },
              { value: "same", label: t("split.grouping_same") },
            ]}
            onChange={(event) => update({ grouping: event.currentTarget.value as GroupingMode })}
          />
          <label className="field-label" htmlFor={`${baseId}-missing`}>
            {t("split.missingLabel")}
          </label>
          <Select
            id={`${baseId}-missing`}
            value={settings.missing}
            disabled={disabled}
            options={[
              { value: "previous", label: t("split.missing_previous") },
              { value: "skip", label: t("split.missing_skip") },
            ]}
            onChange={(event) => update({ missing: event.currentTarget.value as MissingValueMode })}
          />
          <div className="split-inline-actions">
            <Button
              size="sm"
              disabled={disabled || detecting || pageCount < 1 || patternError}
              onClick={onDetect}
            >
              {detecting ? <Spinner aria-label={t("common.loading")} /> : <ScanText size={15} />}
              {detecting && progress.total > 0
                ? t("split.detectProgress", progress)
                : t("split.detectAction")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
