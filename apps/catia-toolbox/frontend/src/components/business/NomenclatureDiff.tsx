import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  identificationApi,
  type NomenclatureCompareDto,
  type NomenclatureCompareMode,
  type NomenclatureMultiCompareDto,
  type NomenclatureRunDto,
} from "../../lib/api";
import { NomenclatureComparisonResult } from "./NomenclatureComparisonResult";
import { NomenclatureMatrix } from "./NomenclatureMatrix";
import { NomenclatureVersionSelector } from "./NomenclatureVersionSelector";

const MAX_VERSIONS = 10;

export function NomenclatureDiff() {
  const { t } = useTranslation();
  const runsQuery = useQuery<NomenclatureRunDto[]>({
    queryKey: ["identification"],
    queryFn: identificationApi.list,
  });
  const runs = runsQuery.data ?? [];
  const defaults = runs.slice(0, 2).reverse().map((run) => run.id);
  const [selection, setSelection] = useState<string[]>([]);
  const [mode, setMode] = useState<NomenclatureCompareMode>("chronology");
  const [referenceId, setReferenceId] = useState("");
  const [addId, setAddId] = useState("");
  const [singleResult, setSingleResult] = useState<NomenclatureCompareDto | null>(null);
  const [multiResult, setMultiResult] = useState<NomenclatureMultiCompareDto | null>(null);
  const [activeComparison, setActiveComparison] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const fileName = (ref: string) => (ref || "").split(/[\\/]/).pop() ?? ref;
  const options = runs.map((run) => ({ value: run.id, label: fileName(run.source_ref) || run.id.slice(0, 8) }));
  const selected = selection.length >= 2 ? selection : defaults;
  const remaining = options.filter((option) => !selected.includes(option.value));
  const candidate = remaining.some((option) => option.value === addId) ? addId : remaining[0]?.value ?? "";
  const effectiveReference = selected.includes(referenceId) ? referenceId : selected[0]!;
  const labelOf = (id: string) => options.find((option) => option.value === id)?.label ?? id.slice(0, 8);

  const mutation = useMutation({
    mutationFn: async () => {
      if (selected.length === 2) {
        return { single: await identificationApi.compare(selected[0]!, selected[1]!), multi: null };
      }
      return {
        single: null,
        multi: await identificationApi.compareMulti(selected, mode, effectiveReference),
      };
    },
    onSuccess: ({ single, multi }) => {
      setError(null);
      setSingleResult(single);
      setMultiResult(multi);
      setActiveComparison(0);
    },
    onError: (err) => setError(err instanceof ApiClientError ? err.message : String(err)),
  });

  const replaceAt = (index: number, value: string) => {
    const next = [...selected];
    const existingIndex = selected.indexOf(value);
    if (existingIndex >= 0) {
      const current = next[index]!;
      next[index] = next[existingIndex]!;
      next[existingIndex] = current;
    } else {
      next[index] = value;
    }
    setSelection(next);
    setSingleResult(null);
    setMultiResult(null);
  };
  const move = (index: number, offset: number) => {
    const next = [...selected];
    [next[index], next[index + offset]] = [next[index + offset]!, next[index]!];
    setSelection(next);
    setMultiResult(null);
  };
  const addVersion = () => {
    if (!candidate || selected.length >= MAX_VERSIONS) return;
    setSelection([...selected, candidate]);
    setAddId("");
    setSingleResult(null);
    setMultiResult(null);
  };
  const removeAt = (index: number) => {
    if (selected.length <= 2) return;
    setSelection(selected.filter((_, current) => current !== index));
    setMultiResult(null);
  };

  const activeResult = multiResult?.comparisons[activeComparison] ?? null;
  const pairLabel = activeResult
    ? `${labelOf(activeResult.base_run_id)} \u2192 ${labelOf(activeResult.other_run_id)}`
    : undefined;

  if (runs.length < 2) {
    return (
      <div className="empty-state">
        <h3 className="card-title">{t("diff.nomenNeedTwo")}</h3>
        <p className="hint">{t("diff.nomenNeedTwoDesc")}</p>
      </div>
    );
  }

  return (
    <div className="form" style={{ maxWidth: "56rem" }}>
      <article className="card">
        <h2 className="card-title">{t("diff.nomenCompareTitle")}</h2>
        <NomenclatureVersionSelector
          options={options}
          selected={selected}
          mode={mode}
          referenceId={effectiveReference}
          pending={mutation.isPending}
          maxVersions={MAX_VERSIONS}
          onReplace={replaceAt}
          onMove={move}
          onRemove={removeAt}
          onModeChange={setMode}
          onReferenceChange={setReferenceId}
          onCompare={() => mutation.mutate()}
        />
        {remaining.length > 0 && selected.length < MAX_VERSIONS ? (
          <div className="row" style={{ marginTop: "0.75rem" }}>
            <select className="input grow" value={candidate} onChange={(event) => setAddId(event.target.value)}>
              {remaining.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <button type="button" className="btn secondary small" onClick={addVersion}>{t("diff.addVersion")}</button>
          </div>
        ) : null}
        <p className="hint">{t("diff.versionLimit", { count: MAX_VERSIONS })}</p>
        {error ? <p className="error">{error}</p> : null}
      </article>

      {multiResult ? (
        <>
          <NomenclatureMatrix result={multiResult} labelOf={labelOf} />
          <article className="card">
            <h2 className="card-title">{t("diff.multiSummaryTitle")}</h2>
            <p className="hint">
              {t("diff.multiSummary", {
                comparisons: multiResult.summary.comparisons ?? 0,
                added: multiResult.summary.added ?? 0,
                removed: multiResult.summary.removed ?? 0,
                changed: multiResult.summary.changed ?? 0,
              })}
            </p>
            <label className="field">
              <span className="field-label">{t("diff.comparisonStep")}</span>
              <select
                className="input"
                value={activeComparison}
                onChange={(event) => setActiveComparison(Number(event.target.value))}
              >
                {multiResult.comparisons.map((comparison, index) => (
                  <option key={`${comparison.base_run_id}-${comparison.other_run_id}`} value={index}>
                    {`${labelOf(comparison.base_run_id)} \u2192 ${labelOf(comparison.other_run_id)}`}
                  </option>
                ))}
              </select>
            </label>
          </article>
        </>
      ) : null}
      {singleResult ? <NomenclatureComparisonResult result={singleResult} /> : null}
      {activeResult ? <NomenclatureComparisonResult result={activeResult} pairLabel={pairLabel} /> : null}
      {!singleResult && !activeResult ? (
        <article className="card"><div className="empty-state"><h3 className="card-title">{t("diff.runPrompt")}</h3></div></article>
      ) : null}
    </div>
  );
}
