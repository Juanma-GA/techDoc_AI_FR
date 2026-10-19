import { useCallback, useRef, useState } from "react";
import { Button } from "@internal/ui";
import { ImagePlus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ImageInputPanel } from "../components/ImageInputPanel";
import { ImagePreview } from "../components/ImagePreview";
import { OcrResults } from "../components/OcrResults";
import { WorkspaceOperations } from "../components/WorkspaceOperations";
import { WorkspaceStatus } from "../components/WorkspaceStatus";
import { useWorkflow } from "../hooks/WorkflowProvider";

type LineSelectionRequest = { lineIndex: number; requestId: number };

export function Home() {
  const { t } = useTranslation();
  const workflow = useWorkflow();
  const [lineSelectionRequest, setLineSelectionRequest] = useState<LineSelectionRequest | null>(null);
  const selectionRequestId = useRef(0);
  const selectRecognizedLine = useCallback((lineIndex: number) => {
    selectionRequestId.current += 1;
    setLineSelectionRequest({ lineIndex, requestId: selectionRequestId.current });
  }, []);
  const handleLineSelection = useCallback((requestId: number) => {
    setLineSelectionRequest((current) => current?.requestId === requestId ? null : current);
  }, []);
  const busy =
    !workflow.storage.ready || workflow.loading || workflow.excelLoading ||
    workflow.excelPairsLoading || workflow.retouching || workflow.restoring || workflow.downloading;

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
            result={workflow.result}
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
