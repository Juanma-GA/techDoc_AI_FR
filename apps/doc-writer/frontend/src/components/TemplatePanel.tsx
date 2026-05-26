import { Badge, Button, FileDropzone, Spinner } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  documentsApi,
  type DocumentDto,
  type ZonesDto,
} from "../lib/api";

type Props = {
  templateDocId: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
};

export function TemplatePanel({ templateDocId, onChange, disabled }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", "template"],
    queryFn: () => documentsApi.list("template"),
  });

  const currentTemplate =
    templateDocId !== null
      ? (templatesQuery.data ?? []).find((d) => d.id === templateDocId)
      : null;

  const zonesQuery = useQuery<ZonesDto, ApiClientError>({
    queryKey: ["documents", templateDocId, "zones"],
    queryFn: () => documentsApi.zones(templateDocId as string),
    enabled: !!templateDocId && !!currentTemplate,
  });

  const refreshZonesMutation = useMutation({
    mutationFn: () => documentsApi.zones(templateDocId as string, true),
    onSuccess: (data) => {
      qc.setQueryData(["documents", templateDocId, "zones"], data);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => documentsApi.upload(files, "template"),
    onSuccess: (res) => {
      setError(null);
      const first = res.uploaded.find((u) => u.ok && u.document_id);
      void qc.invalidateQueries({ queryKey: ["documents", "template"] });
      void qc.invalidateQueries({ queryKey: ["documents"] });
      if (first?.document_id) onChange(first.document_id);
    },
    onError: (err: ApiClientError) => setError(err.message),
  });

  const zones = zonesQuery.data?.zones ?? [];
  const llmUsed = zonesQuery.data?.llm_used ?? false;

  return (
    <div className="flex flex-col gap-2">
      <label className="label">{t("generate.templateLabel")}</label>

      {currentTemplate ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2 rounded-sm border border-md bg-bg-2 p-2">
            <span className="truncate text-sm text-fg">
              {currentTemplate.filename}
            </span>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("generate.templateReanalyse")}
                onClick={() => refreshZonesMutation.mutate()}
                disabled={
                  disabled ||
                  refreshZonesMutation.isPending ||
                  zonesQuery.isLoading
                }
                title={t("generate.templateReanalyse")}
              >
                <RefreshCw
                  size={14}
                  aria-hidden="true"
                  className={
                    refreshZonesMutation.isPending ? "animate-spin" : ""
                  }
                />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("generate.templateClear")}
                onClick={() => onChange(null)}
                disabled={disabled}
              >
                <X size={14} aria-hidden="true" />
              </Button>
            </div>
          </div>

          {zonesQuery.isLoading || refreshZonesMutation.isPending ? (
            <p className="flex items-center gap-2 text-xs text-fg-dim">
              <Spinner size="sm" />{" "}
              {llmUsed || refreshZonesMutation.isPending
                ? t("generate.templateScanningLlm")
                : t("generate.templateScanning")}
            </p>
          ) : zonesQuery.error ? (
            <p className="text-xs text-danger">{zonesQuery.error.message}</p>
          ) : zones.length === 0 ? (
            <p className="text-xs text-warn">
              {t("generate.templateNoZones")}
            </p>
          ) : (
            <div>
              <p className="mb-1 text-xs text-fg-dim">
                {t("generate.templateZonesFound", { count: zones.length })}
                {llmUsed ? ` (${t("generate.templateLlmAssisted")})` : ""}
              </p>
              <ul className="flex flex-col gap-1 max-h-60 overflow-y-auto pr-1">
                {zones.map((z) => {
                  const badge =
                    z.kind === "xxx"
                      ? { variant: "warning" as const, text: "XXX" }
                      : z.kind === "llm"
                        ? { variant: "info" as const, text: "LLM" }
                        : { variant: "default" as const, text: "{{}}" };
                  return (
                    <li
                      key={z.id}
                      className="flex items-center gap-2 text-xs text-fg-dim"
                    >
                      <Badge variant={badge.variant}>{badge.text}</Badge>
                      <span className="font-mono text-fg-dim shrink-0">
                        {z.location}
                      </span>
                      <span className="truncate text-fg">
                        {z.label || "—"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <>
          <FileDropzone
            accept=".pptx"
            multiple={false}
            label={t("generate.templateUploadLabel")}
            description={t("generate.templateUploadDescription")}
            disabled={disabled || uploadMutation.isPending}
            onFiles={(files) => uploadMutation.mutate(files)}
          />
          {uploadMutation.isPending ? (
            <p className="flex items-center gap-2 text-xs text-fg-dim">
              <Spinner size="sm" /> {t("documents.uploading")}
            </p>
          ) : null}
          {error ? <p className="text-xs text-danger">{error}</p> : null}
        </>
      )}
    </div>
  );
}
