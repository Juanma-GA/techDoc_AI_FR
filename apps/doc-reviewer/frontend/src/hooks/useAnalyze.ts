import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { API_BASE_URL } from "../lib/api";
import { useFiltersStore } from "../stores/filtersStore";

type AnalyzeStatus = "idle" | "running" | "done" | "error";

export type QualityState = "analyzable" | "degraded" | "unusable";

export type AnalyzeQuality = {
  state: QualityState;
  coverage: number;
  engine: string;
};

export function useAnalyze(documentId: string | undefined) {
  const qc = useQueryClient();
  const checklistActive = useFiltersStore((s) => s.checklistActive);
  const [status, setStatus] = useState<AnalyzeStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [quality, setQuality] = useState<AnalyzeQuality | null>(null);

  const start = useCallback(async (vision?: boolean) => {
    if (!documentId) return;
    setStatus("running");
    setProgress(0);
    setError(null);
    setQuality(null);

    try {
      // Cible « checklist » (toggle Documents) transmise a chaque run ; `vision`
      // override le reglage persiste le temps d'un run.
      const params = new URLSearchParams({ checklist: String(checklistActive) });
      if (vision !== undefined) params.set("vision", String(vision));
      const url = `${API_BASE_URL}/documents/${documentId}/analyze?${params.toString()}`;
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
  }, [documentId, qc, status, checklistActive]);

  return { status, progress, error, quality, start };
}
