import { Button } from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { wizardApi, type ApiError } from "../lib/api";

type Props = {
  docId: string | null;
  disabled: boolean;
  title?: string;
};

export function WizardZipDownloadButton({ docId, disabled, title }: Props) {
  const { t } = useTranslation();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const downloadZip = async () => {
    if (!docId || disabled || downloading) return;
    setDownloading(true);
    setError(null);
    try {
      const response = await fetch(wizardApi.zipUrl(docId));
      if (!response.ok) {
        const apiError = (await response.json().catch(() => null)) as ApiError | null;
        throw new Error(apiError?.message || response.statusText || "Erreur");
      }
      const disposition = response.headers.get("Content-Disposition");
      const filename =
        disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? `${docId}_dms.zip`;
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="ml-auto">
      <Button
        variant="primary"
        disabled={disabled || downloading}
        aria-busy={downloading}
        title={title}
        onClick={() => void downloadZip()}
      >
        {downloading ? t("migration.analysis.processing") : t("migration.generate.zip")}
      </Button>
      {error ? <div className="error" role="alert">{error}</div> : null}
    </div>
  );
}
