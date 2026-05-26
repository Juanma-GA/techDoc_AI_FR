import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown } from "lucide-react";

import { cn } from "../lib/utils";

export type MultiSelectItem = {
  id: string;
  label: string;
};

export type MultiSelectProps = {
  items: MultiSelectItem[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
  allLabel?: string;
  emptyLabel?: string;
};

/**
 * Sélection multi via Popover Radix. value = [] est interprété par les
 * appelants comme "tous" (pas géré ici — c'est juste une multi-sélection).
 */
export function MultiSelect({
  items,
  value,
  onChange,
  placeholder = "Sélectionner…",
  disabled = false,
  className,
  triggerClassName,
  allLabel,
  emptyLabel = "Aucun élément disponible",
}: MultiSelectProps) {
  const selected = new Set(value);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(Array.from(next));
  };

  const label =
    value.length === 0
      ? allLabel ?? placeholder
      : value.length === 1
        ? (items.find((i) => i.id === value[0])?.label ?? `${value.length} sélection`)
        : `${value.length} sélections`;

  return (
    <Popover.Root>
      <Popover.Trigger
        disabled={disabled || items.length === 0}
        className={cn(
          "inline-flex h-10 w-full items-center justify-between gap-2 rounded-sm border border-md bg-bg-2 px-3 text-left text-fg",
          "hover:bg-card-hover",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light",
          "disabled:cursor-not-allowed disabled:opacity-50",
          triggerClassName,
        )}
      >
        <span className={cn("truncate", value.length === 0 && "text-fg-muted")}>
          {label}
        </span>
        <ChevronDown size={14} className="text-fg-dim" aria-hidden="true" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={4}
          className={cn(
            "z-50 max-h-72 w-[var(--radix-popover-trigger-width)] overflow-auto rounded-sm border border-md bg-card p-1 shadow-card",
            className,
          )}
        >
          {items.length === 0 ? (
            <p className="p-2 text-sm text-fg-muted">{emptyLabel}</p>
          ) : (
            <ul className="flex flex-col">
              {items.map((item) => {
                const isSelected = selected.has(item.id);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => toggle(item.id)}
                      className={cn(
                        "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-2 text-left text-sm text-fg",
                        "hover:bg-card-hover",
                        isSelected && "bg-card-hover",
                      )}
                    >
                      <span className="truncate">{item.label}</span>
                      {isSelected ? (
                        <Check
                          size={14}
                          className="shrink-0 text-brand-blue-light"
                          aria-hidden="true"
                        />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
