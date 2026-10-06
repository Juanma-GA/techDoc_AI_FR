import { AlertTriangle, Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useDocumentExports, type DocumentExport } from "../../hooks/useDocuments";
import { API_BASE_URL } from "../../lib/api";

type Props = {
  documentId: string;
};

export function ExportSelector({ documentId }: Props): JSX.Element {
  const { t } = useTranslation();
  const exportsQuery = useDocumentExports(documentId);
  const [menuOpen, setMenuOpen] = useState(false);
  const options = exportsQuery.data?.available ?? [];

  function download(option: DocumentExport): void {
    const path = option.kind === "commented"
      ? `/documents/${documentId}/commented.pdf`
      : `/documents/${documentId}/export?format=${option.format}`;
    window.open(`${API_BASE_URL}${path}`, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="export-selector" data-testid="export-selector">
      <div
        className="export-menu"
        onMouseEnter={() => setMenuOpen(true)}
        onMouseLeave={() => setMenuOpen(false)}
        onFocus={() => setMenuOpen(true)}
        onBlur={(event) => {
          const next = event.relatedTarget;
          if (!(next instanceof Node) || !event.currentTarget.contains(next)) {
            setMenuOpen(false);
          }
        }}
      >
        <button
          type="button"
          className="btn primary small"
          disabled={exportsQuery.isLoading || options.length === 0}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
        >
          <Download size={14} aria-hidden="true" />
          {t("reviewer.export.download")}
        </button>
        {options.length > 0 ? (
          <div className="export-menu-list" role="menu">
            {options.map((option) => (
              <button
                key={optionKey(option)}
                type="button"
                className="export-menu-option"
                role="menuitem"
                onClick={() => download(option)}
                title={option.warning ?? undefined}
              >
                <span>{option.label}</span>
                {option.warning ? <AlertTriangle size={13} aria-label={option.warning} /> : null}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {exportsQuery.error ? (
        <span className="label" style={{ color: "var(--danger)" }} role="alert">
          {exportsQuery.error instanceof Error ? exportsQuery.error.message : String(exportsQuery.error)}
        </span>
      ) : null}
    </div>
  );
}

function optionKey(option: DocumentExport): string {
  return `${option.kind}:${option.format}`;
}