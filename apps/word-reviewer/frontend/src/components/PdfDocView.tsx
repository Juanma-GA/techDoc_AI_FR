import { useCallback, useEffect, useRef, useState } from "react";

import { documentsApi, type PdfHighlight } from "../lib/api";

type Box = { left: number; top: number; width: number; height: number };

type Props = {
  docId: string;
  page: number;
  version: number; // casse le cache de l'image quand le doc change de version
  highlights: PdfHighlight[];
  selectedId: string | null;
  severityOf: (id: string) => string;
  onSelect: (id: string) => void;
};

/**
 * Rendu fidele d'une page : PNG rasterise cote serveur (docx -> PDF LibreOffice
 * -> PyMuPDF) + calque de surlignage. On MESURE la boite reelle de l'image et on
 * pose l'overlay dessus ; les boxes (en %) tombent pile sur le texte quel que
 * soit le redimensionnement. Meme approche que le pdf-reviewer.
 */
export function PdfDocView({ docId, page, version, highlights, selectedId, severityOf, onSelect }: Props) {
  const [box, setBox] = useState<Box | null>(null);
  const [error, setError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  const measure = useCallback(() => {
    const img = imgRef.current;
    if (!img || !img.clientWidth || !img.clientHeight) return;
    setBox({ left: img.offsetLeft, top: img.offsetTop, width: img.clientWidth, height: img.clientHeight });
  }, []);

  useEffect(() => {
    const img = imgRef.current;
    if (!img || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(img);
    return () => ro.disconnect();
  }, [measure]);

  useEffect(() => {
    setError(false);
    setBox(null);
  }, [docId, page, version]);

  const onPage = highlights.filter((h) => h.page === page);

  return (
    <div className="doc-view pdf-doc-view">
      {error ? (
        <div className="empty-state">Aperçu de page indisponible.</div>
      ) : (
        <div className="pdf-page-wrap">
          <img
            ref={imgRef}
            className="pdf-page-img"
            src={`${documentsApi.pageImageUrl(docId, page)}&v=${version}`}
            alt={`Page ${page}`}
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
              {onPage.flatMap((h) =>
                h.boxes.map((b, i) => {
                  const sev = severityOf(h.id);
                  const cls = [
                    "pdf-hl",
                    sev === "error" ? "error" : sev === "warning" ? "warn" : "info",
                    h.id === selectedId ? "selected" : "",
                  ]
                    .filter(Boolean)
                    .join(" ");
                  return (
                    <button
                      type="button"
                      key={`${h.id}-${i}`}
                      className={cls}
                      data-sug={h.id}
                      onClick={() => onSelect(h.id)}
                      style={{
                        pointerEvents: "auto",
                        position: "absolute",
                        left: `${b.left}%`,
                        top: `${b.top}%`,
                        width: `${b.width}%`,
                        height: `${b.height}%`,
                      }}
                    />
                  );
                }),
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
