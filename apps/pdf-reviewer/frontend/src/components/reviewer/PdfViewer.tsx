import "../../lib/pdfWorker";

import { useEffect, useState } from "react";
import { Document, Page } from "react-pdf";

import type { ViewportLike } from "../../lib/bbox";
import type { Suggestion } from "../../types/domain";
import { HighlightLayer } from "./HighlightLayer";

type Props = {
  pdfUrl: string;
  pageNumber: number;
  zoom: number;
  suggestions: Suggestion[];
  selectedSuggestionId: string | null;
  onSuggestionClick: (id: string) => void;
  onTotalPages: (total: number) => void;
};

export function PdfViewer({
  pdfUrl,
  pageNumber,
  zoom,
  suggestions,
  selectedSuggestionId,
  onSuggestionClick,
  onTotalPages,
}: Props) {
  const [viewport, setViewport] = useState<ViewportLike | null>(null);
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;

  // Reset viewport whenever the PDF source or current page changes — avoids
  // overlay drift while react-pdf re-renders the canvas.
  useEffect(() => {
    setViewport(null);
  }, [pdfUrl, pageNumber, zoom]);

  const filtered = suggestions.filter((s) => s.page === pageNumber);

  return (
    <div className="relative inline-block">
      <Document
        file={pdfUrl}
        onLoadSuccess={({ numPages }) => onTotalPages(numPages)}
        loading={<div className="p-8 text-fg-dim">Loading…</div>}
      >
        <Page
          pageNumber={pageNumber}
          scale={zoom}
          renderTextLayer
          renderAnnotationLayer={false}
          onRenderSuccess={(page) => setViewport(page as unknown as ViewportLike)}
          className="bg-card shadow-card"
        />
      </Document>
      <HighlightLayer
        viewport={viewport}
        dpr={dpr}
        suggestions={filtered}
        selectedSuggestionId={selectedSuggestionId}
        onSuggestionClick={onSuggestionClick}
      />
    </div>
  );
}
