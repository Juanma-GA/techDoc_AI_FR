import type { TFunction } from "i18next";
import { Plus } from "lucide-react";
import { Button } from "@internal/ui";

import type { ReplacementPair } from "../lib/workspace-api";
import { ReplacementPairRow } from "./ReplacementPairRow";

type ReplacementPairsProps = {
  pairs: ReplacementPair[];
  excelPairs: ReplacementPair[];
  showExcelPairs: boolean;
  excelPairsLoading: boolean;
  excelPairsReady: boolean;
  disabled: boolean;
  onAdd: () => void;
  onUpdate: (id: number, field: "reference" | "replacement", value: string) => void;
  onRemove: (id: number) => void;
  onToggle: (id: number) => void;
  onUpdateExcel: ReplacementPairsProps["onUpdate"];
  onRemoveExcel: (id: number) => void;
  onToggleExcel: (id: number) => void;
  t: TFunction;
};

export function ReplacementPairs(props: ReplacementPairsProps) {
  const { pairs, excelPairs, disabled, t } = props;
  const selected = [...pairs, ...excelPairs].filter((pair) => pair.enabled).length;
  return (
    <section aria-labelledby="replacement-pairs-title" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id="replacement-pairs-title" className="label">{t("image.pairsTitle")}</h3>
        <span className="font-mono text-xs text-fg-dim">
          {t("image.selectedPairs", { count: selected, total: pairs.length + excelPairs.length })}
        </span>
      </div>
      {props.showExcelPairs ? (
        <div className="space-y-2 rounded-md border border-md bg-bg-2 p-3">
          <h4 className="text-sm font-medium">{t("image.excelPairsTitle")}</h4>
          {props.excelPairsLoading ? (
            <p role="status" className="text-sm text-fg-dim">{t("image.excelPairsLoading")}</p>
          ) : null}
          {!props.excelPairsLoading && props.excelPairsReady ? (
            excelPairs.length > 0 ? excelPairs.map((pair, index) => (
              <ReplacementPairRow
                key={pair.id} pair={pair} index={index} excel disabled={disabled} t={t}
                onUpdate={props.onUpdateExcel} onRemove={props.onRemoveExcel}
                onToggle={props.onToggleExcel}
              />
            )) : <p className="text-sm text-fg-dim">{t("image.emptyExcelPairs")}</p>
          ) : null}
        </div>
      ) : null}
      {pairs.length > 0 ? pairs.map((pair, index) => (
        <ReplacementPairRow
          key={pair.id} pair={pair} index={index} disabled={disabled} t={t}
          onUpdate={props.onUpdate} onRemove={props.onRemove} onToggle={props.onToggle}
        />
      )) : (
        <p className="rounded-md border border-dashed border-md p-3 text-center text-sm text-fg-dim">
          {t("image.emptyPairs")}
        </p>
      )}
      <Button variant="secondary" className="w-full" disabled={disabled} onClick={props.onAdd}>
        <Plus size={16} aria-hidden="true" />{t("image.addPair")}
      </Button>
      <p className="text-xs leading-relaxed text-fg-dim">{t("image.pairHint")}</p>
      <p className="text-xs leading-relaxed text-fg-dim">{t("image.selectionHint")}</p>
    </section>
  );
}
