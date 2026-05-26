import { Button } from "@internal/ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  sessionsApi,
  type ExportFormat,
} from "../lib/api";

type Props = {
  sessionId: string;
  hasTemplate: boolean;
  filename?: string;
};

const FORMATS: { value: ExportFormat; labelKey: string }[] = [
  { value: "md",   labelKey: "generate.exportMd" },
  { value: "docx", labelKey: "generate.exportDocx" },
  { value: "pdf",  labelKey: "generate.exportPdf" },
  { value: "pptx", labelKey: "generate.exportPptx" },
];


export function ExportButtons({ sessionId, hasTemplate, filename }: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = async (fmt: ExportFormat) => {
    setBusy(fmt);
    setError(null);
    try {
      await sessionsApi.download(sessionId, fmt, filename);
    } catch (err) {
      const msg =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      setError(msg);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        {FORMATS.map((f) => {
          const disabled =
            busy !== null || (f.value === "pptx" && !hasTemplate);
          return (
            <Button
              key={f.value}
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled}
              onClick={() => void download(f.value)}
            >
              {busy === f.value
                ? `${t(f.labelKey)}…`
                : t(f.labelKey)}
            </Button>
          );
        })}
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : null}
      {!hasTemplate ? (
        <p className="text-xs text-fg-dim">{t("generate.exportPptxHint")}</p>
      ) : null}
    </div>
  );
}
