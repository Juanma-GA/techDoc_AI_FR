import { Button, Input } from "@internal/ui";
import { FileSpreadsheet, FileText, FolderOpen } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { BrowseKind } from "../lib/api";

type FieldKind = "source" | "tracker" | "output";
type BrowseAction = { kind: BrowseKind; label: string; icon: ReactNode };

type PathPickerFieldProps = {
  field: FieldKind;
  label: string;
  placeholder: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onBlur: () => void;
  onBrowse: (kind: BrowseKind) => void;
};

export function PathPickerField({
  field,
  label,
  placeholder,
  value,
  disabled,
  onChange,
  onBlur,
  onBrowse,
}: PathPickerFieldProps) {
  const { t } = useTranslation();
  const inputId = `ecm-rename-${field}-path`;
  const actions: BrowseAction[] =
    field === "source"
      ? [
          { kind: "source_file", label: "home.browse_pdf", icon: <FileText aria-hidden="true" className="h-4 w-4" /> },
          {
            kind: "source_directory",
            label: "home.browse_source_folder",
            icon: <FolderOpen aria-hidden="true" className="h-4 w-4" />,
          },
        ]
      : field === "tracker"
        ? [
            {
              kind: "tracker_file",
              label: "home.browse_tracker",
              icon: <FileSpreadsheet aria-hidden="true" className="h-4 w-4" />,
            },
          ]
        : [
            {
              kind: "output_directory",
              label: "home.browse_output_folder",
              icon: <FolderOpen aria-hidden="true" className="h-4 w-4" />,
            },
          ];

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={inputId} className="label">
        {label}
      </label>
      <div className="flex min-w-0 gap-2">
        <Input
          id={inputId}
          className="min-w-0 flex-1"
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.currentTarget.value)}
          onBlur={onBlur}
        />
        {actions.map(({ kind, label: actionLabel, icon }) => (
          <Button
            key={kind}
            type="button"
            variant="secondary"
            size="icon"
            aria-label={t(actionLabel)}
            title={t(actionLabel)}
            disabled={disabled}
            onClick={() => onBrowse(kind)}
          >
            {icon}
          </Button>
        ))}
      </div>
    </div>
  );
}