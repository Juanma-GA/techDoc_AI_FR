import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";

import { cn } from "../lib/utils";
import { selectVariants, type SelectOption, type SelectProps } from "./Select";
import { Button } from "./Button";

export type SelectMenuProps = {
  label: string;
  value: string;
  options: SelectOption[];
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  name?: string;
  id?: string;
  size?: SelectProps["size"];
  state?: SelectProps["state"];
  className?: string;
  triggerClassName?: string;
};

/** Single choice popover for accessible, themeable options outside native menus. */
export function SelectMenu({
  label,
  value,
  options,
  onValueChange,
  placeholder,
  disabled = false,
  name,
  id,
  size,
  state,
  className,
  triggerClassName,
}: SelectMenuProps) {
  const generatedId = useId().replace(/:/g, "");
  const triggerId = id ?? `select-menu-${generatedId}`;
  const listId = `${triggerId}-listbox`;
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [open, setOpen] = useState(false);
  const selectedIndex = options.findIndex((option) => option.value === value);
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : undefined;

  const focusOption = (index: number) => optionRefs.current[index]?.focus();
  const selectOption = (option: SelectOption) => {
    onValueChange(option.value);
    setOpen(false);
  };
  const handleOptionKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusOption(Math.min(index + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusOption(Math.max(index - 1, 0));
    } else if (event.key === "Home") {
      event.preventDefault();
      focusOption(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusOption(options.length - 1);
    }
  };

  return (
    <>
      {name ? <input type="hidden" name={name} value={value} disabled={disabled} /> : null}
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <Button
            id={triggerId}
            type="button"
            variant="secondary"
            size={size}
            disabled={disabled || options.length === 0}
            aria-label={label}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-controls={open ? listId : undefined}
            aria-invalid={state === "error"}
            className={cn(
              selectVariants({ size, state }),
              "flex items-center justify-between gap-2 text-left",
              triggerClassName,
            )}
            onKeyDown={(event) => {
              if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
                event.preventDefault();
                setOpen(true);
              }
            }}
          >
            <span className={cn("truncate", !selectedOption && "text-fg-muted")}>
              {selectedOption?.label ?? placeholder ?? ""}
            </span>
            <ChevronDown size={14} className="shrink-0 text-fg-dim" aria-hidden="true" />
          </Button>
        </Popover.Trigger>
        {open ? (
          <Popover.Portal>
            <Popover.Content
              id={listId}
              role="listbox"
              aria-label={label}
              align="start"
              sideOffset={4}
              collisionPadding={8}
              className={cn(
                "z-50 max-h-72 w-[var(--radix-popover-trigger-width)] overflow-auto rounded-sm border border-md bg-card p-1 shadow-popover",
                className,
              )}
              onOpenAutoFocus={(event) => {
                event.preventDefault();
                focusOption(selectedIndex >= 0 ? selectedIndex : 0);
              }}
            >
              <div className="flex flex-col">
                {options.map((option, index) => {
                  const selected = option.value === value;
                  return (
                    <button
                      key={option.value}
                      ref={(element) => {
                        optionRefs.current[index] = element;
                      }}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      onClick={() => selectOption(option)}
                      onKeyDown={(event) => handleOptionKeyDown(event, index)}
                      className={cn(
                        "flex w-full items-center justify-between gap-2 rounded-sm bg-card px-3 py-2 text-left text-sm text-fg",
                        "hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                        selected && "bg-card-hover",
                      )}
                    >
                      <span className="truncate">{option.label}</span>
                      {selected ? (
                        <Check size={14} className="shrink-0 text-brand-text" aria-hidden="true" />
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </Popover.Content>
          </Popover.Portal>
        ) : null}
      </Popover.Root>
    </>
  );
}
