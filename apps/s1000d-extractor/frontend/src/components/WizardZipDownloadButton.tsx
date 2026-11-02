import { Button, Input, Select } from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { wizardApi } from "../lib/api";
import { formatApiError } from "../lib/migrationUtils";

type Props = {
  docId: string | null;
  disabled: boolean;
  title?: string;
};

type ImageFormat = "original" | "jpeg" | "png";

export function WizardZipDownloadButton({ docId, disabled, title }: Props) {
  const { t } = useTranslation();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [maxDimension, setMaxDimension] = useState("");
  const [imageFormat, setImageFormat] = useState<ImageFormat>("original");

  const parsedDimension = maxDimension.trim() === "" ? undefined : Number(maxDimension);
  const invalidDimension =
    parsedDimension !== undefined &&
    (!Number.isSafeInteger(parsedDimension) || parsedDimension < 1);

  const downloadZip = async () => {
    if (!docId || disabled || downloading || invalidDimension) return;
    setDownloading(true);
    setError(null);
    try {
      const file = await wizardApi.downloadZip(docId, {
        ...(parsedDimension === undefined ? {} : { maxDimension: parsedDimension }),
        format: imageFormat,
      });
      const objectUrl = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = file.name;
      link.hidden = true;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (caught) {
      setError(formatApiError(t, caught));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="ml-auto flex flex-wrap items-end gap-2">
      <label className="flex min-w-36 flex-col gap-1">
        <span className="text-label font-mono uppercase text-fg-dim">
          {t("migration.generate.imageSize")}
        </span>
        <Input
          type="number"
          min="1"
          step="1"
          inputMode="numeric"
          placeholder={t("migration.generate.imageSizePlaceholder")}
          value={maxDimension}
          aria-invalid={invalidDimension}
          aria-describedby={
            invalidDimension
              ? "wizard-image-size-help wizard-image-size-error"
              : "wizard-image-size-help"
          }
          onChange={(event) => setMaxDimension(event.currentTarget.value)}
          disabled={disabled || downloading}
        />
        <span id="wizard-image-size-help" className="sr-only">
          {t("migration.generate.imageSizeHelp")}
        </span>
      </label>
      <label className="flex min-w-36 flex-col gap-1">
        <span className="text-label font-mono uppercase text-fg-dim">
          {t("migration.generate.imageFormat")}
        </span>
        <Select
          value={imageFormat}
          aria-describedby="wizard-image-format-help"
          onChange={(event) => {
            const value = event.currentTarget.value;
            if (value === "original" || value === "jpeg" || value === "png") {
              setImageFormat(value);
            }
          }}
          disabled={disabled || downloading}
          options={[
            { value: "original", label: t("migration.generate.imageFormatOriginal") },
            { value: "jpeg", label: t("migration.generate.imageFormatJpeg") },
            { value: "png", label: t("migration.generate.imageFormatPng") },
          ]}
        />
        <span id="wizard-image-format-help" className="sr-only">
          {t("migration.generate.imageFormatHelp")}
        </span>
      </label>
      <div className="flex flex-col gap-1">
        <Button
          variant="primary"
          className="h-auto py-2.5"
          disabled={disabled || downloading || invalidDimension}
          aria-busy={downloading}
          title={title}
          onClick={() => void downloadZip()}
        >
          {downloading ? t("migration.analysis.processing") : t("migration.generate.zip")}
        </Button>
        {invalidDimension ? (
          <div id="wizard-image-size-error" className="text-sm text-danger" role="alert">
            {t("migration.generate.imageSizeInvalid")}
          </div>
        ) : error ? (
          <div className="text-sm text-danger" role="alert">{error}</div>
        ) : null}
      </div>
    </div>
  );
}
