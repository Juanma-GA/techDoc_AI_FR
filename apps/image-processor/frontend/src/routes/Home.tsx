import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@internal/ui";
import { ImagePlus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ImageInputPanel } from "../components/ImageInputPanel";
import { ImagePreview } from "../components/ImagePreview";
import { OcrResults } from "../components/OcrResults";
import { WorkspaceOperations } from "../components/WorkspaceOperations";
import { WorkspaceStatus } from "../components/WorkspaceStatus";
import { useWorkflow } from "../hooks/WorkflowProvider";
import { withLineBoxOffsets, type LineBoxOffset } from "../lib/replacement-box-offsets";

type LineSelectionRequest = { lineIndex: number; requestId: number };

export function Home() {
  const { t } = useTranslation();
  const workflow = useWorkflow();
  const [lineSelectionRequest, setLineSelectionRequest] = useState<LineSelectionRequest | null>(null);
  const [selectedLineIndex, setSelectedLineIndex] = useState<number | null>(null);
  const [pendingBoxOffsets, setPendingBoxOffsets] = useState<Map<number, { x: number; y: number }>>(
    () => new Map(),
  );
  const lastOperationKind = workflow.document?.operations.at(-1)?.kind;
  useEffect(() => {
    setSelectedLineIndex(null);
    setPendingBoxOffsets(new Map());
  }, [workflow.document?.id]);
  useEffect(() => {
    if (lastOperationKind === "ocr" || lastOperationKind === "undo") {
      setPendingBoxOffsets(new Map());
    }
  }, [workflow.document?.revisions.length, lastOperationKind]);
  const selectionRequestId = useRef(0);
  const selectRecognizedLine = useCallback((lineIndex: number) => {
    setSelectedLineIndex(lineIndex);
    selectionRequestId.current += 1;
    setLineSelectionRequest({ lineIndex, requestId: selectionRequestId.current });
  }, []);
  const selectReplacementBox = useCallback((lineIndex: number) => {
    setSelectedLineIndex(lineIndex);
  }, []);
  const handleLineSelection = useCallback((requestId: number) => {
    setLineSelectionRequest((current) => current?.requestId === requestId ? null : current);
  }, []);
  const busy =
    !workflow.storage.ready || workflow.loading || workflow.excelLoading ||
    workflow.excelPairsLoading || workflow.retouching || workflow.restoring || workflow.downloading;
  const previewResult = useMemo(() => {
    if (!workflow.result) return null;
    const offsets: LineBoxOffset[] = workflow.result.lines.map((line, lineIndex) => {
      const pending = pendingBoxOffsets.get(lineIndex);
      return {
        lineIndex,
        x: pending?.x ?? line.box_offset_x ?? 0,
        y: pending?.y ?? line.box_offset_y ?? 0,
      };
    });
    return withLineBoxOffsets(workflow.result, offsets);
  }, [pendingBoxOffsets, workflow.result]);
  const reapplyBlocked = Boolean(workflow.document?.revisions.some((revision) =>
    revision.kind.startsWith("brush-"),
  ));
  const updatePendingOffsets = useCallback((offsets: LineBoxOffset[]) => {
    setPendingBoxOffsets((current) => {
      const updated = new Map(current);
      offsets.forEach(({ lineIndex, x, y }) => updated.set(lineIndex, { x, y }));
      return updated;
    });
  }, []);
  const applyOffsetsToAll = useCallback(() => {
    const result = previewResult;
    const selectedLine = selectedLineIndex == null ? undefined : result?.lines[selectedLineIndex];
    if (!result || !selectedLine || selectedLineIndex == null) return;
    const replacementLineIndices = new Set(result.references.flatMap((reference) =>
      reference.line_indices.slice(0, reference.replacement_count ?? 0),
    ));
    updatePendingOffsets([...replacementLineIndices].map((lineIndex) => ({
      lineIndex,
      x: selectedLine.box_offset_x ?? 0,
      y: selectedLine.box_offset_y ?? 0,
    })));
  }, [previewResult, selectedLineIndex, updatePendingOffsets]);
  const reapplyReplacements = useCallback(async () => {
    if (previewResult && await workflow.reapplyReplacements(previewResult)) {
      setPendingBoxOffsets(new Map());
    }
  }, [previewResult, workflow.reapplyReplacements]);

  return (
    <div className="space-y-4">
      <header className="page-header">
        <div>
          <h1>{t("home.title")}</h1>
          <p>{t("home.subtitle")}</p>
        </div>
        {workflow.imageFile ? (
          <Button variant="secondary" disabled={busy} onClick={() => void workflow.newImage()}>
            <ImagePlus size={16} aria-hidden="true" />{t("image.newImage")}
          </Button>
        ) : null}
      </header>

      <WorkspaceStatus />
      <form
        onSubmit={workflow.submit}
        className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(20rem,0.82fr)_minmax(0,1.18fr)]"
      >
        <ImageInputPanel workflow={workflow} disabled={busy} t={t} />
        <div className="min-w-0 space-y-4">
          <ImagePreview
            imageFile={workflow.currentFile}
            imageUrl={workflow.imageUrl}
            result={previewResult}
            disabled={busy}
            manuallyEdited={workflow.manuallyEdited}
            canUndo={workflow.canUndo}
            onUndo={workflow.undo}
            onDownload={() => void workflow.downloadImage()}
            onDownloadAs={() => void workflow.downloadImageAs()}
            downloading={workflow.downloading}
            savingAs={workflow.savingAs}
            onImageEdited={workflow.applyBrush}
            onInpaintingChange={workflow.setRetouching}
            onSelectLine={selectRecognizedLine}
            onSelectBox={selectReplacementBox}
            selectedLineIndex={selectedLineIndex}
            reapplyBlocked={reapplyBlocked}
            onUpdateLineOffsets={updatePendingOffsets}
            onApplyOffsetsToAll={applyOffsetsToAll}
            onReapplyReplacements={() => void reapplyReplacements()}
            t={t}
          />
          <OcrResults
            result={workflow.result}
            disabled={busy}
            onReplaceLine={workflow.replaceRecognizedLine}
            onUndoLine={workflow.undoRecognizedLine}
            selectionRequest={lineSelectionRequest}
            onSelectionHandled={handleLineSelection}
            t={t}
          />
        </div>
      </form>
      <WorkspaceOperations operations={workflow.document?.operations ?? []} />
    </div>
  );
}
