import { useDemoMode } from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { loadDemoPdf } from "../../lib/demoPdf";

export function DemoPdfImportButton({
  onFile,
  disabled = false,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const { mode, isReady } = useDemoMode();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isReady || mode !== "demo") return null;

  const importDemoPdf = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      onFile(await loadDemoPdf());
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="form">
      <button
        type="button"
        className="btn secondary"
        disabled={disabled || loading}
        onClick={() => void importDemoPdf()}
      >
        {loading ? t("demo.pdfLoading") : t("documents.upload.importDemo")}
      </button>
      {error ? (
        <p className="error" role="alert">
          {t("demo.pdfLoadError", { message: error })}
        </p>
      ) : null}
    </div>
  );
}
