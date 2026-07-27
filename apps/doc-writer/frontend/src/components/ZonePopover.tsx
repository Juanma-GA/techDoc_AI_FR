import { type ReactNode, useEffect, useRef } from "react";

type Props = {
  x: number;
  y: number;
  meta: string;
  label: string;
  children: ReactNode;
  onClose: () => void;
};

// Popover ancre au clic sur une zone du SVG (parite preview : .zone-popover).
// Position fixed, clamp dans la viewport, ferme sur clic exterieur / Escape.
export function ZonePopover({ x, y, meta, label, children, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    // Differe l'ecoute pour ne pas capter le clic d'ouverture.
    const id = window.setTimeout(
      () => document.addEventListener("click", onDoc, true),
      0,
    );
    document.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(id);
      document.removeEventListener("click", onDoc, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const left = Math.max(8, Math.min(x + 12, window.innerWidth - 380));
  const top = Math.max(8, Math.min(y + 12, window.innerHeight - 180));

  return (
    <div ref={ref} className="zone-popover" style={{ left, top }}>
      <div className="zone-popover-meta">{meta}</div>
      <div className="zone-popover-label">{label}</div>
      <div className="zone-popover-actions">{children}</div>
    </div>
  );
}
