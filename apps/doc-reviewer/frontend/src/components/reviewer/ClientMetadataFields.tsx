import { useTranslation } from "react-i18next";

import type { ClientMappingField } from "../../hooks/useClientConfig";
import type { ClientMetadataDraft } from "./clientMetadataForm";

type Props = {
  entries: [string, ClientMappingField][];
  draft: ClientMetadataDraft;
  locale: string;
  invalidFields: Set<string>;
  onChange: (name: string, value: unknown) => void;
};

export function ClientMetadataFields({
  entries,
  draft,
  locale,
  invalidFields,
  onChange,
}: Props) {
  const { t } = useTranslation();

  return (
    <div className="document-meta-fields">
      {entries.map(([name, definition]) => {
        const label = definition.labels?.[locale] ?? definition.labels?.fr ?? name.replaceAll("_", " ");
        const value = draft[name];
        const formatHint = definition.format_hint?.[locale] ?? definition.format_hint?.fr;
        const invalidFormat = invalidFields.has(name);
        return (
          <label className="field" key={name}>
            <span className="field-label">
              {label}{definition.required ? " *" : ""}
            </span>
            {definition.type === "enum" ? (
              <select
                className="input"
                value={String(value ?? "")}
                onChange={(event) => onChange(name, event.target.value)}
                required={definition.required}
              >
                <option value="">{t("reviewer.meta.valueUnset")}</option>
                {(definition.allowed_values ?? []).map((option) => (
                  <option value={option} key={option}>{option}</option>
                ))}
              </select>
            ) : definition.type === "string_list" ? (
              <textarea
                className="input"
                value={Array.isArray(value) ? value.join("\n") : ""}
                onChange={(event) =>
                  onChange(
                    name,
                    event.target.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
                  )
                }
                maxLength={definition.max_length ?? undefined}
                aria-label={`${label}. ${t("reviewer.meta.listHint")}`}
                title={t("reviewer.meta.listHint")}
                aria-invalid={invalidFormat}
              />
            ) : definition.type === "boolean" ? (
              <input
                type="checkbox"
                checked={value === true}
                onChange={(event) => onChange(name, event.target.checked)}
              />
            ) : (
              <input
                className="input"
                type={definition.type === "integer" || definition.type === "number" ? "number" : "text"}
                step={definition.type === "integer" ? 1 : definition.type === "number" ? "any" : undefined}
                maxLength={definition.max_length ?? undefined}
                value={String(value ?? "")}
                onChange={(event) => onChange(name, event.target.value)}
                required={definition.required}
                aria-invalid={invalidFormat}
              />
            )}
            {formatHint ? <span className="hint">{formatHint}</span> : null}
            {invalidFormat ? (
              <span className="error">{t("reviewer.meta.invalidFormat")}</span>
            ) : null}
          </label>
        );
      })}
    </div>
  );
}
