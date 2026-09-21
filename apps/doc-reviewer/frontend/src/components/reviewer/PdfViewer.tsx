import { useCallback, useEffect, useRef, useState } from "react";

import type { Suggestion } from "../../types/domain";
import { HighlightLayer } from "./HighlightLayer";

type Props = {
  /** URL de l'image PNG de la page courante (rendu serveur). */
  pageImageUrl: string;
  pageNumber: number;
  zoom: number;
  suggestions: Suggestion[];
  selectedSuggestionId: string | null;
  onSuggestionClick: (id: string) => void;
};

type Box = { left: number; top: number; width: number; height: number };

/**
 * Apercu PDF = image PNG rendue cote serveur (`/pages/{n}.png`), affichee a
 * 100% (fit largeur), comme l'ancien preview.html.
 *
 * Alignement des surlignages : on mesure la position et la taille reelles de
 * l'image dans le wrapper, puis on pose le calque exactement sur cette boite.
 * Les overlays (en % via HighlightLayer) restent ainsi alignes quand le
 * viewer est centre ou redimensionne.
 */
export function PdfViewer({
  pageImageUrl,
  pageNumber,
  zoom,
  suggestions,
  selectedSuggestionId,
  onSuggestionClick,
}: Props) {
  const [error, setError] = useState(false);
  const [box, setBox] = useState<Box | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const measure = useCallback(() => {
    const img = imgRef.current;
    const wrapper = wrapRef.current;
    if (!img || !wrapper) return;

    const imageRect = img.getBoundingClientRect();
    const wrapperRect = wrapper.getBoundingClientRect();
    if (!imageRect.width || !imageRect.height || !wrapper.offsetWidth || !wrapper.offsetHeight) return;

    const scaleX = wrapperRect.width / wrapper.offsetWidth || 1;
    const scaleY = wrapperRect.height / wrapper.offsetHeight || 1;
    setBox({
      left: (imageRect.left - wrapperRect.left) / scaleX,
      top: (imageRect.top - wrapperRect.top) / scaleY,
      width: imageRect.width / scaleX,
      height: imageRect.height / scaleY,
    });
  }, []);

  useEffect(() => {
    const img = imgRef.current;
    if (!img || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(img);
    if (wrapRef.current) observer.observe(wrapRef.current);
    return () => observer.disconnect();
  }, [measure]);

  // Reset au changement de page / version.
  useEffect(() => {
    setError(false);
    setBox(null);
  }, [pageImageUrl]);

  const filtered = suggestions.filter((s) => s.page === pageNumber);

  // Fait defiler le viewer jusqu'au surlignage selectionne (clic depuis le
  // panneau de suggestions) : utile quand la page rendue depasse la hauteur
  // de l'ecran et que le surlignage n'est pas deja visible.
  useEffect(() => {
    if (!selectedSuggestionId || !box || !wrapRef.current) return;
    const el = wrapRef.current.querySelector<HTMLElement>(
      `[data-suggestion-id="${selectedSuggestionId}"]`,
    );
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedSuggestionId, box]);

  return (
    <div className="viewer-surface">
      {error ? (
        <div className="empty-state">Apercu de page indisponible.</div>
      ) : (
        <div
          ref={wrapRef}
          className="viewer-wrap"
          style={{
            width: `${zoom * 100}%`,
          }}
        >
          <img
            ref={imgRef}
            className="viewer-img"
            src={pageImageUrl}
            alt=""
            draggable={false}
            onLoad={measure}
            onError={() => setError(true)}
          />
          {box ? (
            <div
              style={{
                position: "absolute",
                left: box.left,
                top: box.top,
                width: box.width,
                height: box.height,
                pointerEvents: "none",
              }}
            >
              <HighlightLayer
                suggestions={filtered}
                selectedSuggestionId={selectedSuggestionId}
                onSuggestionClick={onSuggestionClick}
              />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
