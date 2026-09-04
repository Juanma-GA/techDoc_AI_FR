import { useCallback, useEffect, useRef, useState } from "react";

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

type Box = { left: number; top: number; width: number; height: number };

/**
 * Apercu PDF = image PNG rendue cote serveur (`/pages/{n}.png`), affichee a
 * 100% (fit largeur), comme l'ancien preview.html.
 *
 * Alignement des surlignages : on NE suppose RIEN sur le conteneur. On MESURE
 * la position et la taille reelles de l'image (`offsetLeft/Top`, `clientW/H`)
 * et on pose le calque d'overlays exactement sur cette boite. Les overlays
 * (en % via HighlightLayer) tombent alors pile sur le texte, quelle que soit
 * la facon dont l'image est centree / redimensionnee.
 */
export function PdfViewer({
  pageImageUrl,
  pageNumber,
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
    if (!img || !img.clientWidth || !img.clientHeight) return;
    setBox({
      left: img.offsetLeft,
      top: img.offsetTop,
      width: img.clientWidth,
      height: img.clientHeight,
    });
  }, []);

  // Re-mesure sur changement de taille de l'image (resize fenetre, panneau...).
  useEffect(() => {
    const img = imgRef.current;
    if (!img || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(img);
    return () => ro.disconnect();
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
    <div style={{ width: "100%", textAlign: "center" }}>
      {error ? (
        <div className="empty-state">Apercu de page indisponible.</div>
      ) : (
        <div
          ref={wrapRef}
          className="viewer-wrap"
          style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}
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
