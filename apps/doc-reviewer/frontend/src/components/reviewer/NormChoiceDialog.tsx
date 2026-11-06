import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { DocumentNorm } from "../../hooks/useDocumentNorm";
import { ConfirmDialog } from "../ConfirmDialog";

export type NormChoice = { norm: string; persist: boolean };

type Props = {
  detection: DocumentNorm;
  activeCounts: Record<string, number>;
  onCancel: () => void;
  onConfirm: (choice: NormChoice) => void;
};

export function NormChoiceDialog({ detection, activeCounts, onCancel, onConfirm }: Props) {
  const { t } = useTranslation();
  const detected = detection.detected_norm ?? detection.norms[0]?.code ?? "";
  const [norm, setNorm] = useState(detected);
  const [persist, setPersist] = useState(false);
  const labelOf = (code: string) => detection.norms.find((item) => item.code === code)?.label ?? code;

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
      title={t("reviewer.norm.title")}
      description={t("reviewer.norm.description", { detected: labelOf(detected) })}
      confirmLabel={t("reviewer.norm.run")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => onConfirm({ norm, persist })}
    >
      <fieldset style={{ border: 0, margin: "12px 0 0", padding: 0 }}>
        <legend className="label">{t("reviewer.norm.choose")}</legend>
        {detection.norms.map((item) => (
          <label key={item.code} className="row" style={{ gap: 8, margin: "6px 0" }}>
            <input
              type="radio"
              name="analysis-norm"
              value={item.code}
              checked={norm === item.code}
              onChange={() => setNorm(item.code)}
            />
            <span>{item.label}</span>
            <span className="hint">
              {item.code === detected ? `${t("reviewer.norm.detected")} · ` : ""}
              {t("reviewer.norm.activeRules", { count: activeCounts[item.code] ?? 0 })}
            </span>
          </label>
        ))}
      </fieldset>
      <label className="row" style={{ gap: 8, marginTop: 8 }}>
        <input
          type="checkbox"
          checked={persist}
          onChange={(event) => setPersist(event.target.checked)}
        />
        <span>{t("reviewer.norm.persist", { label: labelOf(norm) })}</span>
      </label>
    </ConfirmDialog>
  );
}
