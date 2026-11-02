import { PdfViewer } from "../reviewer/PdfViewer";
import { SuggestionPanel } from "../reviewer/SuggestionPanel";
import type { Suggestion } from "../../types/domain";

type Props = {
  pageImageUrl: string;
  pageNumber: number;
  zoom: number;
  suggestions: Suggestion[];
  selectedId: string | null;
  focusRequest: number;
  onSuggestionClick: (id: string) => void;
  onSelect: (id: string) => void;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onRejectAll: (ids: string[]) => void;
  onSaveEdit: (id: string, proposedText: string) => void;
  onSaveFeedback: (id: string, feedback: string) => void;
  onUnreject: (id: string) => void;
  onUndo: (id: string) => void;
};

export function PreparationReviewPane({
  pageImageUrl,
  pageNumber,
  zoom,
  suggestions,
  selectedId,
  focusRequest,
  onSuggestionClick,
  onSelect,
  onAccept,
  onReject,
  onRejectAll,
  onSaveEdit,
  onSaveFeedback,
  onUnreject,
  onUndo,
}: Props) {
  return (
    <div className="preparation-review">
      <div className="reviewer-viewer">
        <div className="reviewer-canvas reviewer-canvas-stack">
          <PdfViewer
            pageImageUrl={pageImageUrl}
            pageNumber={pageNumber}
            zoom={zoom}
            suggestions={suggestions}
            selectedSuggestionId={selectedId}
            onSuggestionClick={onSuggestionClick}
          />
        </div>
      </div>
      <SuggestionPanel
        suggestions={suggestions}
        selectedId={selectedId}
        focusRequest={focusRequest}
        onSelect={onSelect}
        onAccept={onAccept}
        onReject={onReject}
        onRejectAll={onRejectAll}
        onSaveEdit={onSaveEdit}
        onSaveFeedback={onSaveFeedback}
        onUnreject={onUnreject}
        onUndo={onUndo}
      />
    </div>
  );
}
