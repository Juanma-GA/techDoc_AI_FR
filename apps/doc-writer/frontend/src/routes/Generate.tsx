import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ExportButtons } from "../components/ExportButtons";
import {
  ApiClientError,
  documentsApi,
  sessionsApi,
  settingsApi,
  streamAsk,
  type DocumentDto,
  type SettingsDto,
} from "../lib/api";
import { useGenerateStore } from "../stores/useGenerateStore";

const STATUS = {
  idle: "",
  streaming: "info",
  done: "ok",
  error: "danger",
} as const;

// Page Generation, pixel-identique au preview (renderGenerate).
export function Generate() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const cancelRef = useRef<(() => void) | null>(null);
  // Suivi du run en cours pour le recap "done" et le message stream vide.
  const startedAtRef = useRef<number>(0);
  const tokenCountRef = useRef<number>(0);
  const firstTokenRef = useRef<boolean>(false);
  const [prompt, setPrompt] = useState("");
  const [feedback, setFeedback] = useState<
    { kind: "ok" | "error"; text: string } | null
  >(null);

  const {
    scopeDocIds,
    templateDocId,
    styleDocId,
    outputLang,
    outputFormat,
    length,
    outputFilename,
    output,
    status,
    currentSessionId,
    setScopeDocIds,
    setTemplateDocId,
    setStyleDocId,
    setOutputLang,
    setOutputFormat,
    setLength,
    setOutputFilename,
    beginStream,
    appendToken,
    finishStream,
    failStream,
    reset,
  } = useGenerateStore();

  const docsQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", "source"],
    queryFn: () => documentsApi.list("source"),
  });
  const templatesQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", "template"],
    queryFn: () => documentsApi.list("template"),
  });
  const stylesQuery = useQuery<DocumentDto[], ApiClientError>({
    queryKey: ["documents", "style"],
    queryFn: () => documentsApi.list("style"),
  });
  const settingsQuery = useQuery<SettingsDto, ApiClientError>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });

  const docs = docsQuery.data ?? [];
  const templates = templatesQuery.data ?? [];
  const styles = stylesQuery.data ?? [];
  const mistralReady = settingsQuery.data?.api_key_set ?? false;
  const isStreaming = status === "streaming";

  const templateDoc = templateDocId
    ? templates.find((d) => d.id === templateDocId)
    : undefined;
  const templateFormat: "pptx" | "docx" | null = templateDoc
    ? templateDoc.filename.toLowerCase().endsWith(".pptx")
      ? "pptx"
      : "docx"
    : null;

  useEffect(
    () => () => {
      cancelRef.current?.();
    },
    [],
  );

  const toggleScope = (id: string) =>
    setScopeDocIds(
      scopeDocIds.includes(id)
        ? scopeDocIds.filter((x) => x !== id)
        : [...scopeDocIds, id],
    );

  const onGenerate = async () => {
    setFeedback(null);
    if (prompt.trim().length < 10) {
      setFeedback({ kind: "error", text: t("generate.tooShort") });
      return;
    }
    if (outputFormat === "template" && !templateDocId) {
      setFeedback({ kind: "error", text: t("generate.templateRequired") });
      return;
    }
    // Etape 1/4 : creation de la session.
    setFeedback({ kind: "ok", text: t("generate.stepCreateSession") });
    let session;
    try {
      session = await sessionsApi.create({
        scope_doc_ids: scopeDocIds,
        lang: outputLang,
        output_format: outputFormat,
        length,
        template_doc_id: templateDocId,
        style_doc_id: styleDocId,
      });
    } catch (err) {
      const msg =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      failStream(msg);
      setFeedback({ kind: "error", text: msg });
      return;
    }
    beginStream(session.id);
    startedAtRef.current = Date.now();
    tokenCountRef.current = 0;
    firstTokenRef.current = false;
    // Etape 2/4 : contact API Mistral (premier round-trip RAG).
    setFeedback({ kind: "ok", text: t("generate.stepContactingMistral") });
    const cancel = streamAsk(session.id, prompt, {
      onSession: () => {
        // Etape 3/4 : connexion etablie, on attend le premier token.
        setFeedback({
          kind: "ok",
          text: t("generate.stepWaitingFirstToken"),
        });
      },
      onToken: (delta) => {
        if (!firstTokenRef.current) {
          firstTokenRef.current = true;
          // Etape 4/4 : streaming en cours.
          setFeedback({ kind: "ok", text: t("generate.stepStreaming") });
        }
        tokenCountRef.current += 1;
        appendToken(delta);
      },
      onDone: () => {
        finishStream();
        cancelRef.current = null;
        if (tokenCountRef.current === 0) {
          // Stream ferme sans aucun token (rare).
          setFeedback({ kind: "error", text: t("generate.streamEmpty") });
        } else {
          const elapsed = ((Date.now() - startedAtRef.current) / 1000).toFixed(
            1,
          );
          setFeedback({
            kind: "ok",
            text: `${t("generate.done")} (${tokenCountRef.current} deltas, ${elapsed}s)`,
          });
        }
        void qc.invalidateQueries({ queryKey: ["sessions"] });
      },
      onError: (message) => {
        failStream(message);
        cancelRef.current = null;
        setFeedback({ kind: "error", text: message });
      },
    });
    cancelRef.current = cancel;
  };

  // streamAsk avale les aborts silencieusement (pas de onError) : on pose donc
  // le message "annule" ici, dans le handler du clic, et non depuis onError.
  const stop = () => {
    cancelRef.current?.();
    cancelRef.current = null;
    finishStream();
    setFeedback({ kind: "error", text: t("generate.aborted") });
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("generate.title")}</h1>
        <p>{t("generate.subtitle")}</p>
      </div>

      {!mistralReady ? (
        <div className="banner warn">
          <strong>{t("generate.mistralRequired")}</strong> {t("generate.mistralHint")}
        </div>
      ) : null}

      {/* Barre d'export */}
      <div className="card">
        <div className="row" style={{ gap: 14 }}>
          <span style={{ minWidth: 160, display: "inline-flex", gap: 8 }}>
            {isStreaming ? <span className="spinner" /> : null}
            <span className={`badge ${STATUS[status]}`}>
              {t(`generate.status.${status}`)}
            </span>
          </span>
          <label className="grow" style={{ minWidth: 220 }}>
            <div className="label">{t("generate.filename")}</div>
            <input
              className="input"
              type="text"
              value={outputFilename}
              placeholder={t("generate.filenamePlaceholder")}
              onChange={(e) => setOutputFilename(e.target.value)}
            />
          </label>
          <ExportButtons
            sessionId={currentSessionId ?? ""}
            hasTemplate={!!templateDocId}
            templateFormat={templateFormat}
            templateDocId={templateDocId}
            filename={outputFilename || undefined}
            ready={status === "done" && !!currentSessionId}
          />
        </div>
        <small
          style={{
            display: "block",
            marginTop: 6,
            color: "var(--fg-dim)",
            fontSize: "0.78rem",
          }}
        >
          {templateFormat === "docx"
            ? t("generate.exportTemplateDocxHint")
            : t("generate.exportPptxHint")}
        </small>
      </div>

      <div className="grid-2">
        <div className="card">
          <h2 className="card-title">{t("generate.promptLabel")}</h2>
          <div className="form">
            <label>
              <div className="label">{t("generate.scopeLabel")}</div>
              <div className="doc-checklist">
                {docs.length === 0 ? (
                  <div className="empty-state">{t("generate.noDocuments")}</div>
                ) : (
                  docs.map((d) => (
                    <label key={d.id}>
                      <input
                        type="checkbox"
                        checked={scopeDocIds.includes(d.id)}
                        onChange={() => toggleScope(d.id)}
                      />
                      <span>{d.filename}</span>
                    </label>
                  ))
                )}
              </div>
            </label>

            <div className="row">
              <label className="grow">
                <div className="label">{t("generate.format")}</div>
                <select
                  className="input"
                  value={outputFormat}
                  disabled={isStreaming}
                  onChange={(e) =>
                    setOutputFormat(e.target.value as typeof outputFormat)
                  }
                >
                  <option value="markdown">{t("generate.formatMarkdown")}</option>
                  <option value="faq">{t("generate.formatFaq")}</option>
                  <option value="structured">{t("generate.formatStructured")}</option>
                  <option value="table">{t("generate.formatTable")}</option>
                  <option value="template">{t("generate.formatTemplate")}</option>
                </select>
              </label>
              <label className="grow">
                <div className="label">{t("generate.length")}</div>
                <select
                  className="input"
                  value={length}
                  disabled={isStreaming}
                  onChange={(e) => setLength(e.target.value as typeof length)}
                >
                  <option value="short">{t("generate.lengthShort")}</option>
                  <option value="medium">{t("generate.lengthMedium")}</option>
                  <option value="long">{t("generate.lengthLong")}</option>
                </select>
              </label>
              <label className="grow">
                <div className="label">{t("generate.outputLang")}</div>
                <select
                  className="input"
                  value={outputLang}
                  disabled={isStreaming}
                  onChange={(e) =>
                    setOutputLang(e.target.value as "fr" | "en" | "es")
                  }
                >
                  <option value="fr">{t("generate.outputLangFr")}</option>
                  <option value="en">{t("generate.outputLangEn")}</option>
                  <option value="es">{t("generate.outputLangEs")}</option>
                </select>
              </label>
            </div>

            <div className="row">
              <label className="grow">
                <div className="label">{t("generate.templateLabel")}</div>
                <select
                  className="input"
                  value={templateDocId ?? ""}
                  disabled={isStreaming}
                  onChange={(e) => setTemplateDocId(e.target.value || null)}
                >
                  <option value="">{t("generate.templateNone")}</option>
                  {templates.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.filename}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grow">
                <div className="label">{t("generate.style")}</div>
                <select
                  className="input"
                  value={styleDocId ?? ""}
                  disabled={isStreaming}
                  onChange={(e) => setStyleDocId(e.target.value || null)}
                >
                  <option value="">{t("generate.styleNone")}</option>
                  {styles.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.filename}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              <div className="label">{t("generate.promptLabel")}</div>
              <textarea
                rows={6}
                value={prompt}
                placeholder={t("generate.promptPlaceholder")}
                disabled={isStreaming}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </label>

            <div className="row">
              {isStreaming ? (
                <button className="btn danger" type="button" onClick={stop}>
                  {t("generate.cancel")}
                </button>
              ) : (
                <button
                  className="btn primary"
                  type="button"
                  disabled={!mistralReady}
                  onClick={() => void onGenerate()}
                >
                  {t("generate.submit")}
                </button>
              )}
              <button
                className="btn ghost"
                type="button"
                onClick={() => {
                  reset();
                  setPrompt("");
                  setFeedback(null);
                }}
              >
                {t("generate.reset")}
              </button>
            </div>
            {feedback ? (
              <div className={feedback.kind === "ok" ? "success" : "error"}>
                {feedback.text}
              </div>
            ) : null}
          </div>
        </div>

        <div className="card">
          <h2 className="card-title">{t("generate.output")}</h2>
          <div className="output">
            {output ? (
              output
            ) : (
              <span style={{ color: "var(--fg-muted)" }}>
                {t("generate.outputEmpty")}
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
