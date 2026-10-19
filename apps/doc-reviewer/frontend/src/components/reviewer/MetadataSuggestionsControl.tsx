import { Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  useSuggestDocumentMetadata,
  type DocumentMetadataSuggestions,
} from "../../hooks/useDocuments";

type Props = {
  documentId: string;
  onApply: (suggestions: DocumentMetadataSuggestions) => void;
};

function countSuggestedFields(suggestions: DocumentMetadataSuggestions): number {
  return [
    suggestions.meta_cmm_number,
    suggestions.meta_pnr_number.length > 0 ? suggestions.meta_pnr_number : null,
    suggestions.meta_revision_number,
    suggestions.meta_revision_date,
    suggestions.meta_first_issue_date,
  ].filter((value) => value !== null && value !== "").length;
}

export function MetadataSuggestionsControl({ documentId, onApply }: Props) {
  const { t } = useTranslation();
  const mutation = useSuggestDocumentMetadata(documentId);
  const suggestedCount = mutation.data ? countSuggestedFields(mutation.data) : 0;

  function detect(): void {
    mutation.reset();
    mutation.mutate(undefined, {
      onSuccess: onApply,
    });
  }

  return (
    <div className="document-meta-panel-actions">
      <div>
        <div className="row">
          <button
            type="button"
            className="btn secondary small"
            onClick={detect}
            disabled={mutation.isPending}
          >
            <Sparkles size={14} aria-hidden="true" />
            {mutation.isPending
              ? t("reviewer.meta.detecting")
              : t("reviewer.meta.detectFromPdf")}
          </button>
        </div>
        {mutation.isError ? (
          <p className="error" role="alert">
            {t("reviewer.meta.detectError", {
              message: mutation.error.message,
            })}
          </p>
        ) : null}
        {mutation.data && !mutation.isError ? (
          <p className="hint" role="status" aria-live="polite">
            {suggestedCount > 0
              ? t("reviewer.meta.detected", {
                  count: suggestedCount,
                  pages: mutation.data.pages_scanned,
                })
              : t("reviewer.meta.noReliableValues")}
          </p>
        ) : null}
      </div>
    </div>
  );
}
