import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  MarkdownView,
  MultiSelect,
  Spinner,
  Textarea,
} from "@internal/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ExportButtons } from "../components/ExportButtons";
import { TemplatePanel } from "../components/TemplatePanel";
import {
  ApiClientError,
  documentsApi,
  sessionsApi,
  streamAsk,
  type DocumentDto,
} from "../lib/api";
import { useGenerateStore } from "../stores/useGenerateStore";

const schema = z.object({
  prompt: z.string().min(10, "min 10 caractères"),
});
type FormValues = z.infer<typeof schema>;

export function Generate() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const cancelRef = useRef<(() => void) | null>(null);

  const {
    scopeDocIds,
    templateDocId,
    output,
    status,
    errorMessage,
    currentSessionId,
    setScopeDocIds,
    setTemplateDocId,
    beginStream,
    appendToken,
    finishStream,
    failStream,
    reset,
  } = useGenerateStore();

  const docsQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents"],
    queryFn: documentsApi.list,
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { prompt: "" },
  });

  useEffect(
    () => () => {
      cancelRef.current?.();
    },
    [],
  );

  const onSubmit = handleSubmit(async (values) => {
    try {
      const session = await sessionsApi.create({
        scope_doc_ids: scopeDocIds,
        lang: i18n.language?.startsWith("en") ? "en" : "fr",
        template_doc_id: templateDocId,
      });
      beginStream(session.id);

      const cancel = streamAsk(session.id, values.prompt, {
        onToken: appendToken,
        onDone: () => {
          finishStream();
          void qc.invalidateQueries({ queryKey: ["sessions"] });
        },
        onError: (message) => failStream(message),
      });
      cancelRef.current = cancel;
    } catch (err) {
      if (err instanceof ApiClientError) failStream(err.message);
      else failStream(err instanceof Error ? err.message : String(err));
    }
  });

  const stop = () => {
    cancelRef.current?.();
    cancelRef.current = null;
    finishStream();
  };

  const documents = docsQuery.data ?? [];
  const items = documents.map((d) => ({ id: d.id, label: d.filename }));
  const hasDocs = documents.length > 0;
  const isStreaming = status === "streaming";

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("generate.title")}</h1>
        <p className="text-fg-dim">{t("generate.subtitle")}</p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("generate.promptLabel")}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="flex flex-col gap-3">
              <label className="label">{t("generate.scopeLabel")}</label>
              <MultiSelect
                items={items}
                value={scopeDocIds}
                onChange={setScopeDocIds}
                allLabel={t("generate.scopeAll")}
                emptyLabel={t("generate.noDocuments")}
                disabled={!hasDocs}
              />

              <TemplatePanel
                templateDocId={templateDocId}
                onChange={setTemplateDocId}
                disabled={isStreaming}
              />

              <label className="label" htmlFor="prompt">
                {t("generate.promptLabel")}
              </label>
              <Textarea
                id="prompt"
                rows={8}
                placeholder={t("generate.promptPlaceholder")}
                state={errors.prompt ? "error" : "default"}
                disabled={isStreaming}
                {...register("prompt")}
              />
              {errors.prompt ? (
                <p className="text-sm text-danger">{errors.prompt.message}</p>
              ) : null}

              <div className="flex items-center gap-2">
                {isStreaming ? (
                  <Button type="button" variant="secondary" onClick={stop}>
                    {t("generate.stop")}
                  </Button>
                ) : (
                  <Button type="submit" disabled={!hasDocs}>
                    {t("generate.submit")}
                  </Button>
                )}
                {status === "done" && output ? (
                  <Button type="button" variant="ghost" onClick={reset}>
                    {t("generate.outputEmpty")}
                  </Button>
                ) : null}
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-2">
                {isStreaming ? <Spinner size="sm" /> : null}
                <span>
                  {isStreaming ? t("generate.submitting") : t("generate.title")}
                </span>
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {status === "error" && errorMessage ? (
              <div className="rounded-sm border border-danger/40 bg-danger/15 p-3 text-sm text-danger">
                <strong>{t("generate.errorTitle")} :</strong> {errorMessage}
              </div>
            ) : null}
            {!output && status !== "error" ? (
              <EmptyState title={t("generate.outputEmpty")} />
            ) : (
              <div className="flex flex-col gap-3">
                <MarkdownView content={output} />
                {status === "done" && currentSessionId ? (
                  <ExportButtons
                    sessionId={currentSessionId}
                    hasTemplate={!!templateDocId}
                  />
                ) : null}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
