import { useEffect, useId, useState, type ReactNode } from "react";

import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { CollapsibleSection } from "./CollapsibleSection";
import { FormField } from "./FormField";
import { Input } from "./Input";
import { Switch } from "./Switch";

export type LlmModelField = "chat" | "embed" | "vision" | "ocr";

export type LlmSettingsValue = {
  llmEnabled: boolean;
  apiKeySet: boolean;
  /** Masked preview such as "sk-...a1b2" (never the key itself). */
  apiKeyPreview?: string | null;
  /** The stored key exists but cannot be decrypted/read. */
  apiKeyUnreadable?: boolean;
  baseUrl: string;
  models: Partial<Record<LlmModelField, string>>;
};

export type LlmSettingsDraft = {
  /** Only present when the user typed a new key (empty keeps the stored key). */
  apiKey?: string;
  baseUrl: string;
  models: Partial<Record<LlmModelField, string>>;
};

export type LlmSettingsLabels = {
  title: string;
  description?: string;
  configured: string;
  notConfigured: string;
  disabled: string;
  enabled: string;
  enabledHint: string;
  apiKey: string;
  /** Hint when a key is stored; may include the preview, e.g. "Saved (sk-...a1b2), leave empty to keep it". */
  apiKeyKeep: string;
  apiKeyUnreadable?: string;
  baseUrl: string;
  models: Partial<Record<LlmModelField, string>>;
  /** Hint under optional model fields (e.g. "Optional: leave empty for chat-only"). */
  optionalModel?: string;
  /** Hint shown until the connection test returned the provider models. */
  modelsHint: string;
  save: string;
  test: string;
  loading: string;
};

export type LlmSettingsFeedback = { kind: "success" | "danger"; message: ReactNode };

export type LlmSettingsPanelProps = {
  /** Current settings; `undefined` while loading. */
  value?: LlmSettingsValue;
  labels: LlmSettingsLabels;
  /** Model inputs to show, in order. Default: chat + embed. */
  modelFields?: LlmModelField[];
  /** Model inputs that may stay empty. Default: embed. */
  optionalModelFields?: LlmModelField[];
  /** Models returned by `POST /api/v1/settings/test`, offered as suggestions (free text stays possible). */
  availableModels?: string[];
  /** Persist the draft. When it returns a promise, the typed key is cleared on success. */
  onSave: (draft: LlmSettingsDraft) => unknown;
  onTest: () => void;
  onToggleEnabled: (enabled: boolean) => void;
  saving?: boolean;
  testing?: boolean;
  toggling?: boolean;
  feedback?: LlmSettingsFeedback | null;
  /** App-specific settings rendered under the standard fields (extra switches, etc.). */
  children?: ReactNode;
  /** Initial open state. Default: open until a key is configured, collapsed afterwards. */
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
};

const DEFAULT_MODEL_FIELDS: LlmModelField[] = ["chat", "embed"];
const DEFAULT_OPTIONAL_FIELDS: LlmModelField[] = ["embed"];

/**
 * Standard Mistral / LLM settings block (STANDARD_POC.md rule #6 and #14):
 * LLM on/off switch (visible even when collapsed), write-only API key, base URL,
 * model fields with provider suggestions, Save + Test connection, feedback.
 * Presentational: the app owns the queries/mutations and the `health` invalidation.
 */
export function LlmSettingsPanel({
  value,
  labels,
  modelFields = DEFAULT_MODEL_FIELDS,
  optionalModelFields = DEFAULT_OPTIONAL_FIELDS,
  availableModels = [],
  onSave,
  onTest,
  onToggleEnabled,
  saving = false,
  testing = false,
  toggling = false,
  feedback,
  children,
  defaultOpen,
  open,
  onOpenChange,
  className,
}: LlmSettingsPanelProps) {
  const modelsListId = useId();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [models, setModels] = useState<Partial<Record<LlmModelField, string>>>({});
  const [internalOpen, setInternalOpen] = useState<boolean | null>(null);

  useEffect(() => {
    if (!value) return;
    setBaseUrl(value.baseUrl);
    setModels(value.models);
  }, [value]);

  const apiKeySet = value?.apiKeySet ?? false;
  const llmEnabled = value?.llmEnabled ?? true;
  const isOpen = open ?? internalOpen ?? defaultOpen ?? !apiKeySet;

  const handleOpenChange = (next: boolean) => {
    if (open === undefined) setInternalOpen(next);
    onOpenChange?.(next);
  };

  const save = () => {
    const draft: LlmSettingsDraft = { baseUrl, models };
    if (apiKey) draft.apiKey = apiKey;
    const result = onSave(draft);
    if (result instanceof Promise) {
      void result.then(() => setApiKey(""), () => undefined);
    }
  };

  const statusBadge = !llmEnabled ? (
    <Badge>{labels.disabled}</Badge>
  ) : apiKeySet ? (
    <Badge variant="success">{labels.configured}</Badge>
  ) : (
    <Badge variant="warning">{labels.notConfigured}</Badge>
  );

  return (
    <CollapsibleSection
      className={className}
      title={labels.title}
      description={labels.description}
      open={isOpen}
      onOpenChange={handleOpenChange}
      aside={
        <div className="flex items-center gap-3">
          {statusBadge}
          <Switch
            checked={llmEnabled}
            onCheckedChange={onToggleEnabled}
            disabled={!value || toggling}
            aria-label={labels.enabled}
          />
        </div>
      }
    >
      {!value ? (
        <p role="status" className="m-0 text-sm text-fg-dim">
          {labels.loading}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="m-0 text-sm text-fg-dim">
            <span className="font-medium text-fg">{labels.enabled}</span> · {labels.enabledHint}
          </p>
          {value.apiKeyUnreadable && labels.apiKeyUnreadable ? (
            <Alert variant="warning">{labels.apiKeyUnreadable}</Alert>
          ) : null}
          <FormField label={labels.apiKey} hint={apiKeySet ? labels.apiKeyKeep : undefined}>
            <Input
              type="password"
              autoComplete="off"
              placeholder={value.apiKeyPreview ?? "sk-..."}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </FormField>
          <FormField label={labels.baseUrl}>
            <Input
              type="url"
              className="font-mono"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
            />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            {modelFields.map((field) => (
              <FormField
                key={field}
                label={labels.models[field] ?? field}
                hint={optionalModelFields.includes(field) ? labels.optionalModel : undefined}
              >
                <Input
                  className="font-mono"
                  list={modelsListId}
                  value={models[field] ?? ""}
                  onChange={(event) =>
                    setModels((current) => ({ ...current, [field]: event.target.value }))
                  }
                />
              </FormField>
            ))}
          </div>
          {availableModels.length === 0 ? (
            <p className="m-0 -mt-2 text-xs text-fg-dim">{labels.modelsHint}</p>
          ) : null}
          <datalist id={modelsListId}>
            {availableModels.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
          {children}
          <div className="flex flex-wrap gap-2">
            <Button disabled={saving} onClick={save}>
              {labels.save}
            </Button>
            <Button variant="secondary" disabled={testing} onClick={onTest}>
              {labels.test}
            </Button>
          </div>
          {feedback ? <Alert variant={feedback.kind}>{feedback.message}</Alert> : null}
        </div>
      )}
    </CollapsibleSection>
  );
}
