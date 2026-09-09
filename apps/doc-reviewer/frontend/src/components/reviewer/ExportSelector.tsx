import { AlertTriangle, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useDocumentExports, type DocumentExport } from "../../hooks/useDocuments";
import { API_BASE_URL } from "../../lib/api";

type Props = {
  documentId: string;
};

export function ExportSelector({ documentId }: Props): JSX.Element {
  const { t } = useTranslation();
  const exportsQuery = useDocumentExports(documentId);
  const [selectedKey, setSelectedKey] = useState("");
  const options = exportsQuery.data?.available ?? [];
  const selected = options.find((option) => optionKey(option) === selectedKey) ?? options[0];

  useEffect(() => {
    if (selected && !options.some((option) => optionKey(option) === selectedKey)) {
      setSelectedKey(optionKey(selected));
    }
  }, [options, selected, selectedKey]);

  function download(): void {
    if (!selected) return;
    const path = selected.kind === "commented"
      ? `/documents/${documentId}/commented.pdf`
      : `/documents/${documentId}/export?format=${selected.format}`;
    window.open(`${API_BASE_URL}${path}`, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="export-selector" data-testid="export-selector">
      <div className="row" style={{ gap: 6, alignItems: "center" }}>
        <Download size={14} aria-hidden="true" />
        <label className="sr-only" htmlFor={`export-format-${documentId}`}>
          {t("reviewer.export.select")}
        </label>
        <select
          id={`export-format-${documentId}`}
          className="input small"
          value={selected ? optionKey(selected) : ""}
          onChange={(event) => setSelectedKey(event.target.value)}
          disabled={exportsQuery.isLoading || options.length === 0}
        >
          {options.length === 0 ? <option value="">{t("reviewer.export.loading")}</option> : null}
          {options.map((option) => (
            <option key={optionKey(option)} value={optionKey(option)}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn primary small"
          onClick={download}
          disabled={!selected || exportsQuery.isLoading}
        >
          {t("reviewer.export.download")}
        </button>
      </div>
      {exportsQuery.error ? (
        <span className="label" style={{ color: "var(--danger)" }} role="alert">
          {exportsQuery.error instanceof Error ? exportsQuery.error.message : String(exportsQuery.error)}
        </span>
      ) : null}
      {selected?.warning ? (
        <div className="banner warn" role="note" style={{ marginTop: 6 }}>
          <AlertTriangle size={14} aria-hidden="true" />
          <span>{selected.warning}</span>
        </div>
      ) : null}
    </div>
  );
}

function optionKey(option: DocumentExport): string {
  return `${option.kind}:${option.format}`;
}