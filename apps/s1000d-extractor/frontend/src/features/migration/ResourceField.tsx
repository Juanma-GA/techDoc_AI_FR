import { type ReactNode, useId, useState } from "react";
import { Button, FileDropzone } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { CircleHelp, FileText } from "lucide-react";
import { ConfirmButton } from "../../components/ConfirmButton";

export function matchesAccept(file: File, accept: string) {
  const name = file.name.toLowerCase();
  return accept.split(",").some((ext) => name.endsWith(ext.trim().toLowerCase()));
}

export function ResourceField({ label, hint, help, accept, filename, disabled = false, status, onSelect, onClear }: {
  label: string; hint?: string; help?: string; accept: string; filename?: string; disabled?: boolean;
  status?: ReactNode; onSelect: (file: File) => void; onClear?: () => void;
}) {
  const { t } = useTranslation();
  const helpId = useId();
  const [helpOpen, setHelpOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formats = accept.split(",").map((ext) => ext.trim().replace(".", "")).join(" / ");
  return <div className="flex flex-col gap-2">
    <div className="flex items-center gap-1">
      <span className="font-medium">{label}</span>
      {help ? <Button type="button" variant="ghost" size="sm" className="h-6 w-6 px-0"
        aria-label={t("migration.upload.helpToggle", { label })} aria-expanded={helpOpen}
        aria-controls={helpId} onClick={() => setHelpOpen((open) => !open)}>
        <CircleHelp size={15} aria-hidden="true" />
      </Button> : null}
    </div>
    {hint ? <span className="text-sm text-fg-dim">{hint}</span> : null}
    {help ? <p id={helpId} hidden={!helpOpen} className="rounded-sm border bg-bg-2 p-3 text-sm text-fg-dim">
      {help}
    </p> : null}
    <FileDropzone accept={accept} multiple={false} disabled={disabled} className="p-4"
      label={t("migration.upload.dropLabel")} description={formats}
      onFiles={(files) => {
        const file = files[0];
        if (!file) return;
        if (!matchesAccept(file, accept)) {
          setError(t("migration.upload.wrongFormat", { formats }));
          return;
        }
        setError(null);
        onSelect(file);
      }} />
    {error ? <span role="alert" className="text-sm text-danger">{error}</span> : null}
    {status}
    {filename ? <div className="flex items-center gap-2 rounded-sm border bg-bg-2 px-3 py-1.5" role="status">
      <FileText size={16} className="shrink-0 text-fg-dim" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate text-sm" title={filename}>{filename}</span>
      {onClear ? <ConfirmButton label={t("migration.ui.clearResource")} variant="ghost" size="sm"
        disabled={disabled} onConfirm={onClear} /> : null}
    </div> : null}
  </div>;
}
