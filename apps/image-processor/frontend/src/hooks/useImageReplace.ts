import type { TFunction } from "i18next";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useDemoMode } from "@internal/ui";

import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { analysisForm, hasValidManualPairs } from "../lib/analysis-form";
import {
  requestError, restoreFile, storeFile, workspaceApi, type ReplacementPair,
} from "../lib/workspace-api";
import { useExcelMapping, type ExcelMemorySnapshot } from "./useExcelMapping";
import { useImageDocument } from "./useImageDocument";
import { useImageDownload } from "./useImageDownload";
import { useRecognizedTextReplacement } from "./useRecognizedTextReplacement";
import { useRecognizedTextUndo } from "./useRecognizedTextUndo";
import { useWorkspaceStorage } from "./useWorkspaceStorage";

export type { ReplacementPair } from "../lib/workspace-api";

type PendingAutoOcr = { pieceRow: string; requestId: number };
type DemoWorkspaceBackup = {
  document: ReturnType<typeof useImageDocument>["document"];
  excel: ReturnType<typeof useExcelMapping>["persistenceState"];
  manualPairs: ReplacementPair[];
};

function emptyExcelSnapshot(): ExcelMemorySnapshot {
  return {
    workbook: null,
    sheets: [],
    sheet: "",
    columns: [],
    referenceColumn: "",
    replacementColumn: "",
    icnColumn: "",
    pieceColumn: "",
    pieces: [],
    pieceRow: "",
    pairs: [],
  };
}

async function saveExcelSnapshot(snapshot: ExcelMemorySnapshot) {
  await workspaceApi.saveExcel({
    workbook: snapshot.workbook ? await storeFile(snapshot.workbook) : null,
    sheets: snapshot.sheets,
    sheet: snapshot.sheet,
    columns: snapshot.columns,
    referenceColumn: snapshot.referenceColumn,
    replacementColumn: snapshot.replacementColumn,
    icnColumn: snapshot.icnColumn,
    pieceColumn: snapshot.pieceColumn,
    pieces: snapshot.pieces,
  });
}

export function useImageReplace(t: TFunction) {
  const { mode, isReady: demoModeReady } = useDemoMode();
  const [replacementPairs, setReplacementPairs] = useState<ReplacementPair[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [retouching, setRetouching] = useState(false);
  const [demoWorkspaceActive, setDemoWorkspaceActive] = useState(mode === "demo");
  const [demoWorkspacePrepared, setDemoWorkspacePrepared] = useState(mode !== "demo");
  const demoWorkspaceBackup = useRef<DemoWorkspaceBackup | null>(null);
  const [pendingAutoOcr, setPendingAutoOcr] = useState<PendingAutoOcr | null>(null);
  const autoOcrRequestId = useRef(0);
  const startedAutoOcrRequestId = useRef<number | null>(null);
  const ocrRunningRef = useRef(false);
  const excel = useExcelMapping(t);
  const image = useImageDocument(t);
  const download = useImageDownload({ image, excel, setError, t });
  const storage = useWorkspaceStorage({
    excel: excel.persistenceState, restoreExcel: excel.restoreExcel,
    excelPending: excel.excelLoading || (excel.excelSelectionConfigured && !excel.excelPairsReady),
    document: image.document, manualPairs: replacementPairs,
    suspendPersistence: !demoModeReady || mode === "demo" || demoWorkspaceActive,
  });
  const captureDemoWorkspace = useCallback(async () => {
    if (demoWorkspaceBackup.current) return;
    await storage.flush();
    if (demoWorkspaceBackup.current) return;
    const previousDocumentIsDemo =
      image.document?.source.name.toLocaleUpperCase() === "IMAGE_ROUE.PNG";
    const previousWorkbookIsDemo =
      excel.excelFile?.name.toLocaleUpperCase() === "DEMO_ROUE.XLSX";
    demoWorkspaceBackup.current = {
      document: previousDocumentIsDemo ? null : image.document,
      excel: previousWorkbookIsDemo ? emptyExcelSnapshot() : excel.persistenceState,
      manualPairs: previousDocumentIsDemo ? [] : replacementPairs,
    };
    setDemoWorkspaceActive(true);
    setDemoWorkspacePrepared(true);
  }, [storage.flush, image.document, excel.excelFile, excel.persistenceState, replacementPairs]);
  useEffect(() => {
    if (mode === "demo" && !demoWorkspaceBackup.current) {
      setDemoWorkspacePrepared(false);
    }
  }, [mode]);
  useEffect(() => {
    if (mode !== "demo" || !storage.ready || demoWorkspaceBackup.current) return;
    void captureDemoWorkspace().catch((requestFailure: unknown) => {
      setError(requestError(requestFailure, t("image.errorGeneric")));
    });
  }, [mode, storage.ready, captureDemoWorkspace, t]);
  const recognizedTextOptions = {
    image, manualPairs: replacementPairs, setManualPairs: setReplacementPairs,
    excel, loading, restoring, downloading: download.downloading, retouching, setLoading, setError, t,
  };
  const replaceRecognizedLine = useRecognizedTextReplacement(recognizedTextOptions);
  const undoRecognizedLine = useRecognizedTextUndo(recognizedTextOptions);

  function selectExcelPieceRow(pieceRow: string) {
    excel.setExcelPieceRow(pieceRow);
    if (!pieceRow) {
      setPendingAutoOcr(null);
      return;
    }
    setPendingAutoOcr({ pieceRow, requestId: ++autoOcrRequestId.current });
  }

  async function chooseImage(files: File[]) {
    setPendingAutoOcr(null);
    setRestoring(true);
    setError("");
    try {
      await storage.flush();
      if (image.chooseImage(files)) {
        setReplacementPairs([]);
        excel.resetPiece();
        return true;
      }
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
    } finally {
      setRestoring(false);
    }
  }

  async function newImage() {
    setPendingAutoOcr(null);
    setRestoring(true);
    setError("");
    try {
      await storage.flush();
      image.clear();
      setReplacementPairs([]);
      excel.resetPiece();
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
    } finally {
      setRestoring(false);
    }
  }

  async function loadDemoFiles() {
    await captureDemoWorkspace();
    const [imageResponse, workbookResponse] = await Promise.all([
      fetch(`${import.meta.env.BASE_URL}demo/Image_roue.png`),
      fetch(`${import.meta.env.BASE_URL}demo/DEMO_ROUE.xlsx`),
    ]);
    if (!imageResponse.ok || !workbookResponse.ok) {
      throw new Error(t("settings.demo.importError"));
    }

    const [imageBlob, workbookBlob] = await Promise.all([
      imageResponse.blob(), workbookResponse.blob(),
    ]);
    const imageFile = new File([imageBlob], "Image_roue.png", { type: "image/png" });
    const workbookFile = new File([workbookBlob], "DEMO_ROUE.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    if (!await chooseImage([imageFile])) {
      throw new Error(t("settings.demo.importError"));
    }
    if (!await excel.chooseExcel([workbookFile], {
      preferredSheetName: "PDE",
      fallbackSheetIndex: 2,
      referenceColumn: "C",
      replacementColumn: "E",
      icnColumn: "AD",
      pieceColumn: "F",
    })) {
      throw new Error(t("settings.demo.importError"));
    }
  }

  async function leaveDemoWorkspace() {
    setPendingAutoOcr(null);
    setRestoring(true);
    setError("");
    try {
      const backup = demoWorkspaceBackup.current;
      let normalExcel: ExcelMemorySnapshot;
      if (backup) {
        normalExcel = backup.excel;
        image.restoreDocument(backup.document);
        excel.restoreMemory(backup.excel);
        setReplacementPairs(backup.manualPairs);
      } else {
        const savedPreset = await workspaceApi.readExcel();
        normalExcel = savedPreset.workbook?.name.toLocaleUpperCase() === "DEMO_ROUE.XLSX"
          ? emptyExcelSnapshot()
          : {
              ...savedPreset,
              workbook: savedPreset.workbook ? restoreFile(savedPreset.workbook) : null,
              pieceRow: "",
              pairs: [],
            };
        image.clear();
        setReplacementPairs([]);
        excel.restoreMemory(normalExcel);
      }
      await saveExcelSnapshot(normalExcel);
      demoWorkspaceBackup.current = null;
      setDemoWorkspaceActive(false);
      setDemoWorkspacePrepared(true);
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("settings.demo.restoreError")));
      throw requestFailure;
    } finally {
      setRestoring(false);
    }
  }

  function updatePair(id: number, field: "reference" | "replacement", value: string) {
    setReplacementPairs((current) =>
      current.map((pair) => pair.id === id ? { ...pair, [field]: value } : pair),
    );
  }
  function togglePair(id: number) {
    setReplacementPairs((current) =>
      current.map((pair) => pair.id === id ? { ...pair, enabled: !pair.enabled } : pair),
    );
  }
  function addPair() {
    setReplacementPairs((current) => [
      ...current, {
        id: Math.max(-1, ...current.map((pair) => pair.id)) + 1,
        reference: "", replacement: "", enabled: true,
      },
    ]);
  }
  function removePair(id: number) {
    setReplacementPairs((current) => current.filter((pair) => pair.id !== id));
  }

  async function runOcr() {
    if (
      !image.currentFile || !image.imageFile || loading || restoring ||
      retouching || download.downloading || ocrRunningRef.current
    ) return;
    ocrRunningRef.current = true;
    setLoading(true);
    setError("");
    try {
      const form = analysisForm(
        image.currentFile, image.imageFile.name, replacementPairs, excel, t,
        image.result?.replacement_font_size,
        true,
      );
      image.applyOcr(await imageReplaceApi.runOcr(form));
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
    } finally {
      ocrRunningRef.current = false;
      setLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runOcr();
  }

  const runOcrRef = useRef(runOcr);
  runOcrRef.current = runOcr;

  useEffect(() => {
    const pending = pendingAutoOcr;
    if (!pending) return;
    if (pending.pieceRow !== excel.excelPieceRow) {
      setPendingAutoOcr((current) =>
        current?.requestId === pending.requestId ? null : current,
      );
      return;
    }
    if (
      !image.currentFile || !image.imageFile || !excel.excelSelectionReady ||
      !storage.ready || loading || restoring || retouching || download.downloading
    ) return;

    if (startedAutoOcrRequestId.current === pending.requestId) return;
    startedAutoOcrRequestId.current = pending.requestId;
    setPendingAutoOcr((current) =>
      current?.requestId === pending.requestId ? null : current,
    );
    void runOcrRef.current();
  }, [
    pendingAutoOcr,
    excel.excelPieceRow,
    excel.excelSelectionReady,
    excel.excelPairs,
    image.currentFile,
    image.imageFile,
    image.result?.replacement_font_size,
    storage.ready,
    loading,
    restoring,
    retouching,
    download.downloading,
    replacementPairs,
  ]);

  async function reapplyReplacements(resultOverride?: OcrResultDto): Promise<boolean> {
    const result = resultOverride ?? image.result;
    if (!image.imageFile || !result || loading || restoring || retouching) return false;

    const references = result.references
      .map((reference, index) => ({ reference, index }))
      .filter(({ reference }) => reference.replacement);
    if (references.length === 0) return false;

    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("image", image.imageFile, image.imageFile.name);
      form.append(
        "lines_json",
        JSON.stringify(result.lines.map(({ text, box }) => ({ text, box }))),
      );
      form.append(
        "replacement_pairs_json",
        JSON.stringify(references.map(({ reference }) => ({
          reference: reference.reference,
          replacement: reference.replacement,
        }))),
      );
      form.append(
        "broadcast_references_json",
        JSON.stringify([...new Set(references
          .filter(({ reference }) => reference.found)
          .map(({ reference }) => reference.reference))]),
      );
      if (result.replacement_font_size != null) {
        form.append("replacement_font_size", String(result.replacement_font_size));
      }
      const rendered = await imageReplaceApi.reapplyReplacements(form);
      const referencesWithCounts = result.references.map((reference, index) => {
        const renderedIndex = references.findIndex((item) => item.index === index);
        const replacementCount = renderedIndex < 0
          ? reference.replacement_count
          : rendered.replacement_counts[renderedIndex];
        return {
          ...reference,
          ...(replacementCount === undefined ? {} : { replacement_count: replacementCount }),
        };
      });
      image.applyTextReplacement({
        ...result,
        edited_image: rendered.edited_image,
        references: referencesWithCounts,
        replacement_font_size: rendered.replacement_font_size,
      });
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("image.errorGeneric")));
      return false;
    } finally {
      setLoading(false);
    }
  }

  async function openHistory(id: string) {
    setPendingAutoOcr(null);
    setRestoring(true);
    setError("");
    try {
      await storage.flush();
      const entry = await workspaceApi.read(id);
      excel.restoreExcel(entry.state.excel);
      setReplacementPairs(entry.state.manualPairs);
      image.restore(id, entry.state);
      return true;
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("history.loadError")));
      return false;
    } finally {
      setRestoring(false);
    }
  }

  async function retrySave() {
    setError("");
    try {
      await storage.flush();
    } catch (requestFailure) {
      setError(requestError(requestFailure, t("history.saveError")));
    }
  }

  return {
    ...excel, ...image, storage, replacementPairs, error, loading,
    canRunOcr: excel.excelSelectionReady || hasValidManualPairs(replacementPairs),
    demoWorkspacePrepared,
    downloading: download.downloading, savingAs: download.savingAs, restoring, retouching,
    setRetouching, loadDemoFiles, leaveDemoWorkspace,
    chooseImage, newImage, updatePair, togglePair, addPair, removePair, submit,
    setExcelPieceRow: selectExcelPieceRow,
    replaceRecognizedLine, undoRecognizedLine, reapplyReplacements, openHistory,
    downloadImage: download.downloadImage,
    downloadImageAs: download.downloadImageAs,
    retrySave,
  };
}
