import { useCallback, useEffect, useMemo, useState } from "react";

import { storeFile, workspaceApi, type ExcelSnapshot, type ReplacementPair } from "../lib/workspace-api";
import type { ExcelMemorySnapshot } from "./useExcelMapping";
import type { useImageDocument } from "./useImageDocument";
import { useQueuedSave } from "./useQueuedSave";

async function serializeExcel(memory: ExcelMemorySnapshot): Promise<ExcelSnapshot> {
  return { ...memory, workbook: memory.workbook ? await storeFile(memory.workbook) : null };
}

type StorageOptions = {
  excel: ExcelMemorySnapshot;
  excelPending: boolean;
  restoreExcel: (snapshot: ExcelSnapshot) => void;
  document: ReturnType<typeof useImageDocument>["document"];
  manualPairs: ReplacementPair[];
};

export function useWorkspaceStorage({
  excel, excelPending, restoreExcel, document, manualPairs,
}: StorageOptions) {
  const [ready, setReady] = useState(false);
  const [startupError, setStartupError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setStartupError(null);
    void workspaceApi.readExcel().then((preset) => {
      if (!active) return;
      restoreExcel({ ...preset, pieceRow: "", pairs: [] });
      setReady(true);
    }).catch((error: unknown) => {
      if (active) setStartupError(error);
    });
    return () => { active = false; };
  }, [attempt, restoreExcel]);

  const preset = useMemo(() => ready ? {
    workbook: excel.workbook, sheets: excel.sheets, sheet: excel.sheet, columns: excel.columns,
    referenceColumn: excel.referenceColumn, replacementColumn: excel.replacementColumn,
    icnColumn: excel.icnColumn, pieceColumn: excel.pieceColumn, pieces: excel.pieces,
  } : null, [
    ready, excel.workbook, excel.sheets, excel.sheet, excel.columns, excel.referenceColumn,
    excel.replacementColumn, excel.icnColumn, excel.pieceColumn, excel.pieces,
  ]);
  const presetSave = useQueuedSave(preset, async (memory) =>
    workspaceApi.saveExcel({
      ...memory, workbook: memory.workbook ? await storeFile(memory.workbook) : null,
    }),
  );
  const snapshot = useMemo(
    () => ready && document && !excelPending ? { document, excel, manualPairs } : null,
    [ready, document, excelPending, excel, manualPairs],
  );
  const historySave = useQueuedSave(snapshot, async (memory) =>
    workspaceApi.save(memory.document.id, {
      schema_version: 1,
      image: await storeFile(memory.document.source),
      excel: await serializeExcel(memory.excel),
      manualPairs: memory.manualPairs,
      revisions: memory.document.revisions,
      operations: memory.document.operations,
    }),
  );
  const flush = useCallback(async () => {
    await presetSave.flush();
    await historySave.flush();
  }, [presetSave.flush, historySave.flush]);

  return {
    ready, startupError, saving: presetSave.saving || historySave.saving,
    saveError: historySave.error ?? presetSave.error,
    historySaved: historySave.saved, flush,
    retryStartup: () => setAttempt((count) => count + 1),
  };
}
