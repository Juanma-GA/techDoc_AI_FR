import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  ApiRequestError, documentsApi, pdfCutApi, startWizardStream, wizardApi,
  type PdfCutDetection, type WizardState,
} from "../../lib/api";
import { formatApiError } from "../../lib/migrationUtils";
import { needsDmrlReview } from "../../lib/wizardReview";
import { useMigrationStore } from "./useMigrationStore";
import type { MigrationInputs } from "./useMigrationInputs";

type PdfCut = {
  docId: string; detection: PdfCutDetection; selectedTitle: string;
  startPage: number | null; endPage: number | null;
};
export type StartProgressState = { pct: number; label: string };

export function useMigrationWizard(inputs: MigrationInputs) {
  const { docId: routeId } = useParams<{ docId: string }>();
  const docId = routeId ?? null;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [wiz, setWiz] = useState<WizardState | null>(null);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState<StartProgressState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reused, setReused] = useState(false);
  const [pdfCut, setPdfCut] = useState<PdfCut | null>(null);
  const [pdfCutBusy, setPdfCutBusy] = useState(false);
  const flush = useRef<(() => Promise<boolean>) | null>(null);
  const stream = useRef<AbortController | null>(null);
  const active = useRef<string | null>(docId);
  const skipLoad = useRef<string | null>(null);
  const request = useRef(0);
  const alive = useRef(true);
  const route = useRef(docId);
  route.current = docId;
  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["s1000d-docs"] });
    void qc.invalidateQueries({ queryKey: ["s1000d-images"] });
  }, [qc]);
  const failed = useCallback((value: unknown) => setError(formatApiError(t, value)), [t]);

  const normalize = async (id: string, initial: WizardState, includeSplit = false) => {
    let state = initial;
    if (state.step === "dmrl" && !needsDmrlReview(state)) state = await wizardApi.action(id, "advance", {});
    if (includeSplit && state.step === "split") state = await wizardApi.action(id, "advance", {});
    return state;
  };
  const startAnalysis = async (id: string) => {
    stream.current?.abort();
    const controller = new AbortController();
    stream.current = controller;
    setStarting({ pct: 5, label: t("migration.start.starting") });
    try {
      const state = await startWizardStream(id, (event, data) => {
        if (active.current !== id) return;
        if (event === "progress") setStarting({
          pct: typeof data.pct === "number" ? data.pct : 0,
          label: t(`migration.start.${String(data.step)}`, { defaultValue: t("migration.start.fallback") }),
        });
      }, controller.signal);
      if (active.current === id) {
        setPdfCut(null);
        setWiz(await normalize(id, state));
      }
    } finally {
      if (stream.current === controller) {
        stream.current = null;
        setStarting(null);
      }
      refresh();
    }
  };
  const startDocument = async (id: string, sourceFormat: string) => {
    if (sourceFormat === "pdf") {
      const detection = await pdfCutApi.detect(id);
      if (active.current !== id) return;
      if (detection.dmrl_titles.length || (detection.validation_required &&
          (detection.selected_page == null || detection.selected_end_page == null))) {
        setPdfCut({
          docId: id, detection, selectedTitle: detection.dmrl_titles[0] ?? "",
          startPage: detection.selected_page ?? detection.default_start_page,
          endPage: detection.selected_end_page ?? detection.total_pages,
        });
        return;
      }
    }
    await startAnalysis(id);
  };
  const load = async (id: string) => {
    const ticket = ++request.current;
    active.current = id;
    setBusy(true);
    setError(null);
    setWiz(null);
    setPdfCut(null);
    try {
      let state: WizardState;
      try {
        state = await wizardApi.get(id);
      } catch (value) {
        if (!(value instanceof ApiRequestError) || value.code !== "WIZARD_NOT_STARTED") throw value;
        const document = await documentsApi.get(id);
        if (ticket === request.current) await startDocument(id, document.source_format);
        return;
      }
      if (ticket === request.current) setWiz(state);
    } catch (value) {
      if (ticket === request.current && !(value instanceof DOMException && value.name === "AbortError")) failed(value);
    } finally {
      if (ticket === request.current) setBusy(false);
    }
  };
  useEffect(() => {
    if (!inputs.ready || inputs.loading) return;
    if (!docId) {
      const previous = useMigrationStore.getState().currentDocId;
      if (previous) navigate(`/migration/${previous}`, { replace: true });
      return;
    }
    useMigrationStore.getState().patch({ currentDocId: docId });
    if (skipLoad.current === docId) {
      skipLoad.current = null;
      return;
    }
    void load(docId);
    return () => {
      request.current += 1;
      if (active.current === docId) stream.current?.abort();
    };
  }, [docId, inputs.ready, inputs.loading, inputs.mode]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      request.current += 1;
      stream.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (wiz?.step !== "preliminary") flush.current = null;
  }, [wiz?.step]);
  useEffect(() => {
    const reset = () => {
      stream.current?.abort();
      useMigrationStore.getState().reset(inputs.mode);
      setWiz(null);
      setPdfCut(null);
      setStarting(null);
      navigate("/migration", { replace: true });
    };
    window.addEventListener("s1000d-documents-reset", reset);
    return () => window.removeEventListener("s1000d-documents-reset", reset);
  }, [inputs.mode, navigate]);

  const beforeLeaving = async () => !flush.current || await flush.current();
  const start = async () => {
    if (!await beforeLeaving()) return;
    const originalRoute = route.current;
    let startedFor: string | null = null;
    setError(null);
    setReused(false);
    setBusy(true);
    setWiz(null);
    try {
      const { document, resourcesChanged } = await inputs.upload();
      if (!alive.current || route.current !== originalRoute) return;
      startedFor = document.id;
      active.current = document.id;
      skipLoad.current = docId !== document.id ? document.id : null;
      useMigrationStore.getState().patch({ currentDocId: document.id });
      navigate(`/migration/${document.id}`);
      setReused(document.reused === true);
      if (document.reused && !resourcesChanged) {
        try {
          setWiz(await wizardApi.get(document.id));
          return;
        } catch (value) {
          if (!(value instanceof ApiRequestError) || value.code !== "WIZARD_NOT_STARTED") throw value;
        }
      }
      await startDocument(document.id, document.source_format);
    } catch (value) {
      if (alive.current && (startedFor ? active.current === startedFor : route.current === originalRoute) &&
          !(value instanceof DOMException && value.name === "AbortError")) failed(value);
    } finally {
      if (alive.current && (startedFor ? active.current === startedFor : route.current === originalRoute)) setBusy(false);
      refresh();
    }
  };
  const open = async (id: string) => {
    if (!await beforeLeaving()) return;
    useMigrationStore.getState().patch({ currentDocId: id });
    if (docId === id) await load(id);
    else navigate(`/migration/${id}`);
  };
  const action = async (name: string, params?: Record<string, unknown>): Promise<boolean> => {
    if (!docId) { setError(t("migration.ui.noDocument")); return false; }
    if (!await beforeLeaving()) return false;
    setBusy(true);
    setError(null);
    try {
      setWiz(await wizardApi.action(docId, name, params));
      refresh();
      return true;
    } catch (value) {
      failed(value);
      return false;
    } finally { setBusy(false); }
  };
  const validateAndGenerate = async () => {
    if (!docId || !await beforeLeaving()) return;
    setBusy(true);
    setError(null);
    try { setWiz(await normalize(docId, await wizardApi.get(docId), true)); refresh(); }
    catch (value) { failed(value); }
    finally { setBusy(false); }
  };
  const remove = async (id: string) => {
    if (!await beforeLeaving()) return;
    try {
      await documentsApi.delete(id, crypto.randomUUID());
      const draft = useMigrationStore.getState();
      if (draft.uploaded?.document.id === id) draft.patch({ uploaded: null });
      if (docId === id) {
        draft.patch({ currentDocId: null });
        setWiz(null);
        navigate("/migration", { replace: true });
      }
      refresh();
    } catch (value) { failed(value); }
  };
  const confirmPdfCut = async () => {
    if (!pdfCut || pdfCut.startPage == null || pdfCut.endPage == null) {
      setError(t("migration.upload.pdfCut.invalidRange")); return;
    }
    setPdfCutBusy(true);
    setError(null);
    try {
      await pdfCutApi.confirm(pdfCut.docId, pdfCut.startPage, pdfCut.endPage);
      const id = pdfCut.docId;
      setPdfCut(null);
      await startAnalysis(id);
    } catch (value) { failed(value); }
    finally { setPdfCutBusy(false); }
  };
  const redetect = async (title: string) => {
    if (!pdfCut) return;
    setPdfCutBusy(true);
    try {
      const detection = await pdfCutApi.detect(pdfCut.docId, title);
      setPdfCut({ ...pdfCut, detection, selectedTitle: title,
        startPage: detection.default_start_page, endPage: pdfCut.endPage ?? detection.total_pages });
    } catch (value) { failed(value); }
    finally { setPdfCutBusy(false); }
  };
  return {
    docId, wiz, busy, starting, error, reused, pdfCut, pdfCutBusy, setPdfCut,
    start, open, action, remove, confirmPdfCut, redetect, validateAndGenerate,
    onFlushReady: useCallback((handler: (() => Promise<boolean>) | null) => { flush.current = handler; }, []),
  };
}
export type MigrationWizard = ReturnType<typeof useMigrationWizard>;
