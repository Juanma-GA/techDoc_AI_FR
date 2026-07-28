import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { useStandards } from "../../hooks/useStandards";
import type { Standard } from "../../types/domain";

type Props = {
  standardId: string | null;
  versionId: string | null;
  onChange: (standardId: string | null, versionId: string | null) => void;
};

const TRANSVERSE_VALUE = "__transverse__";

export function StandardPicker({ standardId, versionId, onChange }: Props): JSX.Element {
  const { t } = useTranslation();
  const standards = useStandards();
  const items: Standard[] = standards.data ?? [];

  const current = useMemo(
    () => items.find((s) => s.id === standardId) ?? null,
    [items, standardId],
  );
  const versions = current?.versions ?? [];

  // Auto-select the only version when there is exactly one.
  useEffect(() => {
    if (!current) return;
    const onlyVersion = versions.length === 1 ? versions[0] : undefined;
    if (onlyVersion && onlyVersion.id !== versionId) {
      onChange(current.id, onlyVersion.id);
    }
    if (versionId && !versions.some((v) => v.id === versionId)) {
      onChange(current.id, versions[0]?.id ?? null);
    }
  }, [current, versions, versionId, onChange]);

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-xs text-fg-dim">
        <span className="label">{t("standards.selectStandard")}</span>
        <select
          value={standardId ?? TRANSVERSE_VALUE}
          onChange={(e) => {
            const value = e.target.value;
            if (value === TRANSVERSE_VALUE) {
              onChange(null, null);
              return;
            }
            const next = items.find((s) => s.id === value);
            const firstVersion = next?.versions[0]?.id ?? null;
            onChange(value, firstVersion);
          }}
          className="min-w-[16rem] rounded-sm border bg-bg-2 px-2 py-1 text-fg"
        >
          <option value={TRANSVERSE_VALUE}>{t("standards.transverse")}</option>
          {items.map((s) => (
            <option key={s.id} value={s.id}>
              {s.code} — {s.label}
              {s.builtin ? "" : ` (${t("standards.custom")})`}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-fg-dim">
        <span className="label">{t("standards.selectVersion")}</span>
        <select
          disabled={!current || versions.length === 0}
          value={versionId ?? ""}
          onChange={(e) => onChange(standardId, e.target.value || null)}
          className="min-w-[10rem] rounded-sm border bg-bg-2 px-2 py-1 text-fg disabled:opacity-50"
        >
          <option value="" disabled>
            {versions.length === 0 ? t("standards.noVersion") : t("standards.selectVersion")}
          </option>
          {versions.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label}
              {v.builtin ? "" : ` (${t("standards.custom")})`}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
