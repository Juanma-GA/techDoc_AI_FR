import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { API_BASE_URL, api, CSRF_HEADERS } from "../lib/api";
import { useClientConfig } from "./useClientConfig";
import { useFiltersStore } from "../stores/filtersStore";
import { missingDocumentContext } from "../types/domain";
import type { Document, Suggestion } from "../types/domain";

type AnalyzeStatus = "idle" | "running" | "done" | "error";

export type QualityState = "analyzable" | "degraded" | "unusable";

export type AnalyzeQuality = {
  state: QualityState;
  coverage: number;
  engine: string;
};

export type AnalyzeOptions = {
  vision?: boolean;
  firstPage?: number;
  lastPage?: number;
  modifiedOnly?: boolean;
  pageNumber?: number;
  pageOverrides?: Record<number, boolean>;
};

export type PageRevisionStatus = {
  page: number;
  is_modified: boolean | null;
  source: "detected" | "manual";
};

export function useAnalyze(
  documentId: string | undefined,
  document?: Document,
  previousRevisionFile?: File | null,
) {
  const qc = useQueryClient();
  const clientConfig = useClientConfig();
  const legacyChecklistActive = useFiltersStore((s) => s.checklistActive);
  const checklistActive =
    import.meta.env.VITE_LEGACY_RULES_UI === "true" && legacyChecklistActive;
  const requiredFields = clientConfig.data
    ? Object.entries(clientConfig.data.mapping.fields)
        .filter(([, field]) => field.required)
        .map(([name]) => name)
    : undefined;
  const missingContextFields = missingDocumentContext(document, requiredFields);
  const contextReady = Boolean(document) && missingContextFields.length === 0;
  const parseProgressIsIndeterminate = document?.working_format === "docx";
  const [status, setStatus] = useState<AnalyzeStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [progressIndeterminate, setProgressIndeterminate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quality, setQuality] = useState<AnalyzeQuality | null>(null);
  // Avertissements non bloquants (ex. scan checklist/IA interrompu par une
  // erreur Mistral) : l'analyse se termine quand meme (statut "done"), mais
  // le resultat peut etre incomplet — ne doit jamais passer inaperçu.
  const [warnings, setWarnings] = useState<string[]>([]);
  const [pageStatuses, setPageStatuses] = useState<PageRevisionStatus[]>([]);
  const [pageOverrides, setPageOverrides] = useState<Record<number, boolean>>({});

  useEffect(() => {
    setPageStatuses([]);
    setPageOverrides({});
  }, [documentId]);

  const start = useCallback(async (options: AnalyzeOptions = {}) => {
    if (!documentId) return;
    if (!contextReady) {
      setStatus("error");
      setError("DOCUMENT_CONTEXT_INCOMPLETE");
      return;
    }
    setStatus("running");
    setProgress(0);
    setProgressIndeterminate(parseProgressIsIndeterminate);
    setError(null);
    setQuality(null);
    setWarnings([]);

    try {
      // Cible « checklist » (toggle Documents) transmise a chaque run ; `vision`
      // override le reglage persiste le temps d'un run.
      const params = new URLSearchParams({ checklist: String(checklistActive) });
      if (options.vision !== undefined) params.set("vision", String(options.vision));
      if (options.firstPage !== undefined) params.set("first_page", String(options.firstPage));
      if (options.lastPage !== undefined) params.set("last_page", String(options.lastPage));
      if (options.modifiedOnly !== undefined) {
        params.set("modified_only", String(options.modifiedOnly));
      }
      if (options.pageNumber !== undefined) {
        params.set("page_number", String(options.pageNumber));
      }
      const overrides = options.pageOverrides ?? pageOverrides;
      if (Object.keys(overrides).length > 0) {
        params.set("page_overrides", JSON.stringify(overrides));
      }
      const url = `${API_BASE_URL}/documents/${documentId}/analyze?${params.toString()}`;
      const body = new FormData();
      if (previousRevisionFile) {
        body.append("previous_revision_file", previousRevisionFile);
      }
      const response = await fetch(url, {
        method: "POST",
        headers: { Accept: "text/event-stream", ...CSRF_HEADERS },
        body: previousRevisionFile ? body : undefined,
      });
      if (!response.ok || !response.body) {
        let message = `HTTP ${response.status}`;
        try {
          const payload = (await response.json()) as { message?: string; code?: string };
          message = payload.message ?? payload.code ?? message;
        } catch {
          /* keep the HTTP fallback */
        }
        throw new Error(message);
      }
      const suggestionsKey = ["suggestions", documentId] as const;
      await qc.cancelQueries({ queryKey: suggestionsKey });
      qc.setQueryData<Suggestion[]>(suggestionsKey, (current) => {
        if (!current) return current;
        return current.filter((suggestion) =>
          suggestion.status === "applied" ||
          suggestion.status === "rejected" ||
          (options.pageNumber !== undefined && suggestion.page !== options.pageNumber),
        );
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        // sse-starlette emet des lignes CRLF ("\r\n") : normaliser en LF avant
        // de decouper sur "\n\n", sinon aucun bloc n'est jamais detecte (la
        // sous-chaine "\n\n" n'existe pas dans "\r\n\r\n") et rien ne se met a
        // jour (jauge figee a 0%, "done" jamais recu via ce parsing).
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let idx = buffer.indexOf("\n\n");
        while (idx !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              const data = line.slice(5).trim();
              if (currentEvent === "progress") {
                try {
                  const parsed = JSON.parse(data) as {
                    step?: string;
                    pct?: number;
                    total?: number;
                  };
                  if (typeof parsed.pct === "number") setProgress(parsed.pct);
                  setProgressIndeterminate(
                    parsed.step === "parse" &&
                      parseProgressIsIndeterminate &&
                      typeof parsed.total !== "number",
                  );
                } catch {
                  /* ignore */
                }
              } else if (currentEvent === "quality") {
                try {
                  const parsed = JSON.parse(data) as Partial<AnalyzeQuality>;
                  if (parsed.state) {
                    setQuality({
                      state: parsed.state as QualityState,
                      coverage: typeof parsed.coverage === "number" ? parsed.coverage : 0,
                      engine: parsed.engine ?? "pdf",
                    });
                  }
                } catch {
                  /* ignore */
                }
              } else if (currentEvent === "page_statuses") {
                try {
                  const parsed = JSON.parse(data) as { pages?: PageRevisionStatus[] };
                  if (Array.isArray(parsed.pages)) setPageStatuses(parsed.pages);
                } catch {
                  /* ignore */
                }
              } else if (currentEvent === "suggestion") {
                try {
                  const parsed = JSON.parse(data) as Suggestion;
                  if (parsed.id && parsed.document_id === documentId) {
                    qc.setQueryData<Suggestion[]>(["suggestions", documentId], (current) => {
                      const suggestions = current ?? [];
                      if (suggestions.some((suggestion) => suggestion.id === parsed.id)) {
                        return suggestions;
                      }
                      return [...suggestions, parsed].sort(
                        (left, right) =>
                          left.page - right.page || left.created_at.localeCompare(right.created_at),
                      );
                    });
                  }
                } catch {
                  /* ignore */
                }
              } else if (currentEvent === "done") {
                setStatus("done");
                setProgress(100);
              } else if (currentEvent === "warning") {
                try {
                  const parsed = JSON.parse(data) as { messages?: string[] };
                  if (Array.isArray(parsed.messages)) setWarnings(parsed.messages);
                } catch {
                  /* ignore */
                }
              } else if (currentEvent === "error") {
                setStatus("error");
                try {
                  const parsed = JSON.parse(data) as { code?: string; message?: string };
                  setError(parsed.message ?? parsed.code ?? "error");
                } catch {
                  setError("error");
                }
              }
            }
          }
          idx = buffer.indexOf("\n\n");
        }
      }
      qc.invalidateQueries({ queryKey: ["suggestions", documentId] });
      qc.invalidateQueries({ queryKey: ["rule-results", documentId] });
      qc.invalidateQueries({ queryKey: ["document", documentId] });
      if (status !== "error") setStatus("done");
    } catch (exc) {
      if (documentId) {
        qc.invalidateQueries({ queryKey: ["suggestions", documentId] });
      }
      setStatus("error");
      setError(exc instanceof Error ? exc.message : "error");
    }
  }, [contextReady, documentId, pageOverrides, previousRevisionFile, qc, status, checklistActive, parseProgressIsIndeterminate]);

  const correctPageStatus = useCallback((pageNumber: number, isModified: boolean) => {
    const nextOverrides = { ...pageOverrides, [pageNumber]: isModified };
    setPageOverrides(nextOverrides);
    setPageStatuses((current) =>
      current.map((page) =>
        page.page === pageNumber
          ? { ...page, is_modified: isModified, source: "manual" }
          : page,
      ),
    );
    if (isModified) {
      void start({
        modifiedOnly: false,
        pageNumber,
        pageOverrides: nextOverrides,
      });
    } else if (documentId) {
      void api
        .delete<void>(`/documents/${documentId}/pages/${pageNumber}/suggestions`)
        .then(() => qc.invalidateQueries({ queryKey: ["suggestions", documentId] }))
        .catch((exc: unknown) => {
          setStatus("error");
          setError(exc instanceof Error ? exc.message : "error");
        });
    }
  }, [documentId, pageOverrides, qc, start]);

  return {
    status,
    progress,
    progressIndeterminate,
    error,
    quality,
    warnings,
    pageStatuses,
    start,
    correctPageStatus,
    contextReady,
    missingContextFields,
  };
}
