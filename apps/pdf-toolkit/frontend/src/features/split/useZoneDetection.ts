import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { TFunction } from "i18next";

import type { ZoneSettings } from "./SplitValuesPanel";
import { extractValue, fullPageZone, groupPageValues, type SplitRow } from "./splitModel";
import { readZoneTextsForDocument } from "./zoneText";

export type DetectFeedback = { tone: "success" | "warning" | "error"; message: string };

type Options = {
  documentProxy: PDFDocumentProxy | null;
  settings: ZoneSettings;
  pattern: RegExp | null;
  patternError: boolean;
  t: TFunction;
};

/** Identifies the parameters a detection depends on, to know when the table is out of date. */
function detectionKey(settings: ZoneSettings): string {
  const zone = settings.scope === "page" ? fullPageZone : settings.zone;
  return JSON.stringify([zone, settings.valueType, settings.customPattern, settings.grouping, settings.missing]);
}

export function useZoneDetection({ documentProxy, settings, pattern, patternError, t }: Options) {
  const [detecting, setDetecting] = useState(false);
  const [progress, setProgress] = useState({ completed: 0, total: 0 });
  const [feedback, setFeedback] = useState<DetectFeedback | null>(null);
  const [lastKey, setLastKey] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const lastDocumentRef = useRef<PDFDocumentProxy | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const stale = lastKey !== detectionKey(settings) || lastDocumentRef.current !== documentProxy;

  const reset = () => {
    controllerRef.current?.abort();
    setFeedback(null);
    setLastKey(null);
    lastDocumentRef.current = null;
  };

  /** Reads every page and returns the grouped rows, or null when nothing usable was found. */
  const detect = async (): Promise<SplitRow[] | null> => {
    if (patternError) return null;
    if (!documentProxy) {
      setFeedback({ tone: "error", message: t("split.detectNotReady") });
      return null;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const key = detectionKey(settings);
    setDetecting(true);
    setFeedback(null);
    try {
      const texts = await readZoneTextsForDocument(
        documentProxy,
        settings.scope === "page" ? fullPageZone : settings.zone,
        (completed, total) => setProgress({ completed, total }),
        controller.signal,
      );
      const values = texts.map((text) => extractValue(text, pattern));
      if (!values.some((value) => value.trim())) {
        setFeedback({
          tone: "error",
          message: t(texts.some((text) => text.trim()) ? "split.detectNoMatch" : "split.detectNoText"),
        });
        return null;
      }
      const result = groupPageValues(values, settings.grouping, settings.missing);
      setLastKey(key);
      lastDocumentRef.current = documentProxy;
      const summary = t("split.detectSummary", {
        documents: result.rows.length,
        missing: result.missingPages.length,
      });
      setFeedback(
        result.rows.length === 1 && documentProxy.numPages > 1
          ? {
              tone: "warning",
              message: `${summary} ${t("split.detectSingleValue", { value: result.rows[0]?.value ?? "" })}`,
            }
          : { tone: "success", message: summary },
      );
      return result.rows;
    } catch (reason) {
      if (!controller.signal.aborted && !(reason instanceof DOMException && reason.name === "AbortError")) {
        setFeedback({ tone: "error", message: t("split.detectFailed") });
      }
      return null;
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setDetecting(false);
        setProgress({ completed: 0, total: 0 });
      }
    }
  };

  return { detecting, progress, feedback, stale, detect, reset };
}
