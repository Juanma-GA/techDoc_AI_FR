/**
 * Slicer — rangee de "pills" cliquables pour selectionner un sous-ensemble.
 *
 * Une pill "Tous" (valeur []) deselectionne le reste ; cliquer une pill projet
 * deselectionne "Tous". Si plus aucune pill projet n'est active, on retombe sur
 * "Tous". `value = []` est interprete par les appelants comme "tous".
 * Utilise par le Manager (perimetre KPIs) et le Chatbot (perimetre conversation).
 */
import { type ReactNode } from "react";

import { cn } from "../lib/utils";

export type SlicerItem = {
  id: string;
  label: string;
};

export type SlicerProps = {
  items: SlicerItem[];
  /** Liste des ids selectionnes. `[]` = tous (pill "Tous" active). */
  value: string[];
  onChange: (next: string[]) => void;
  allLabel: string;
  className?: string;
};

function SlicerPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
        active
          ? "border-brand bg-brand text-brand-fg"
          : "border-md bg-bg-2 text-fg-dim hover:bg-card-hover hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

export function Slicer({ items, value, onChange, allLabel, className }: SlicerProps) {
  const allActive = value.length === 0;
  const selected = new Set(value);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    // Vide => [] = "tous" (la pill "Tous" reprend la main automatiquement).
    onChange(Array.from(next));
  };

  return (
    <div className={cn("flex flex-wrap gap-2", className)} role="group">
      <SlicerPill active={allActive} onClick={() => onChange([])}>
        {allLabel}
      </SlicerPill>
      {items.map((item) => (
        <SlicerPill
          key={item.id}
          active={selected.has(item.id)}
          onClick={() => toggle(item.id)}
        >
          {item.label}
        </SlicerPill>
      ))}
    </div>
  );
}
