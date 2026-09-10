import { useEffect, useRef, useState } from "react";

import type { Suggestion } from "../../types/domain";
import { HighlightLayer } from "./HighlightLayer";

type Props = {
  /** URL de l'image PNG de la page courante (rendu serveur). */
  pageImageUrl: string;
  pageNumber: number;
  suggestions: Suggestion[];
  selectedSuggestionId: string | null;
  onSuggestionClick: (id: string) => void;
};

/**
 * Apercu PDF = image PNG rendue cote serveur (`/pages/{n}.png`), affichee a
 * 100% (fit largeur), comme l'ancien preview.html.
 *
 * Alignement des surlignages : le wrapper est le seul repere de position et
 * le calque couvre exactement l'image. Les overlays (en % via
 * HighlightLayer) restent ainsi alignes pendant le redimensionnement.
 */
export function PdfViewer({
  pageImageUrl,
  pageNumber,
  suggestions,
  selectedSuggestionId,
  onSuggestionClick,
}: Props) {
  const [error, setError] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Reset au changement de page / version.
  useEffect(() => {
    setError(false);
  }, [pageImageUrl]);

  const filtered = suggestions.filter((s) => s.page === pageNumber);

  // Fait defiler le viewer jusqu'au surlignage selectionne (clic depuis le
  // panneau de suggestions) : utile quand la page rendue depasse la hauteur
  // de l'ecran et que le surlignage n'est pas deja visible.
  useEffect(() => {
    if (!selectedSuggestionId || !wrapRef.current) return;
    const el = wrapRef.current.querySelector<HTMLElement>(
      `[data-suggestion-id="${selectedSuggestionId}"]`,
    );
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedSuggestionId]);

  return (
    <div style={{ width: "100%", textAlign: "center" }}>
      {error ? (
        <div className="empty-state">Apercu de page indisponible.</div>
      ) : (
        <div
          ref={wrapRef}
          className="viewer-wrap"
          style={{
            position: "relative",
            display: "inline-block",
            maxWidth: "100%",
            lineHeight: 0,
          }}
        >
          <img
            className="viewer-img"
            src={pageImageUrl}
            alt=""
            draggable={false}
            style={{ display: "block", maxWidth: "100%", height: "auto" }}
            onError={() => setError(true)}
          />
          <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
            <HighlightLayer
              suggestions={filtered}
              selectedSuggestionId={selectedSuggestionId}
              onSuggestionClick={onSuggestionClick}
            />
          </div>
        </div>
      )}
    </div>
  );
}
