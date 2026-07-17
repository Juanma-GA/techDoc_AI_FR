import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { API_BASE_URL } from "../lib/api";

type AnalyzeStatus = "idle" | "running" | "done" | "error";

export function useAnalyze(documentId: string | undefined) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<AnalyzeStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async (vision?: boolean) => {
    if (!documentId) return;
    setStatus("running");
    setProgress(0);
    setError(null);

    try {
      // `vision` override le reglage persiste (.../settings/mistral) le temps
      // d'un run — c'est la checkbox "Inclure la vision (Pixtral)" du preview.
      const url =
        vision === undefined
          ? `${API_BASE_URL}/documents/${documentId}/analyze`
          : `${API_BASE_URL}/documents/${documentId}/analyze?vision=${vision}`;
      const response = await fetch(url, {
        method: "POST",
        headers: { Accept: "text/event-stream" },
      });
      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
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
                  const parsed = JSON.parse(data) as { pct?: number };
                  if (typeof parsed.pct === "number") setProgress(parsed.pct);
                } catch {
                  /* ignore */
                }
              } else if (currentEvent === "done") {
                setStatus("done");
                setProgress(100);
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
      qc.invalidateQueries({ queryKey: ["document", documentId] });
      if (status !== "error") setStatus("done");
    } catch (exc) {
      setStatus("error");
      setError(exc instanceof Error ? exc.message : "error");
    }
  }, [documentId, qc, status]);

  return { status, progress, error, start };
}
