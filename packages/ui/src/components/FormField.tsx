import {
  Children,
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
  useId,
} from "react";

import { cn } from "../lib/utils";
import { Input } from "./Input";
import { Select } from "./Select";
import { Textarea } from "./Textarea";

const STATEFUL_CONTROLS: unknown[] = [Input, Select, Textarea];

export type FormFieldProps = {
  label: ReactNode;
  children: ReactElement;
  /** Id given to the control; generated when omitted. */
  id?: string;
  hint?: ReactNode;
  /** Translated error message; marks the control aria-invalid. */
  error?: ReactNode;
  required?: boolean;
  /** Visually marks required fields; the text comes from the caller's i18n. */
  requiredLabel?: string;
  className?: string;
};

/**
 * Label + control + hint/error with the accessibility wiring done once:
 * `htmlFor`/`id`, `aria-describedby`, `aria-invalid`, `aria-required`.
 * The single child must be a form control (`Input`, `Select`, `Textarea`...).
 */
export function FormField({
  label,
  children,
  id,
  hint,
  error,
  required,
  requiredLabel,
  className,
}: FormFieldProps) {
  const generatedId = useId();
  const controlId = id ?? (children.props as { id?: string }).id ?? generatedId;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const child = Children.only(children);

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={controlId} className="text-sm font-medium text-fg">
        {label}
        {required ? (
          <span className="ml-0.5 text-danger" aria-hidden="true" title={requiredLabel}>
            *
          </span>
        ) : null}
      </label>
      {isValidElement(child)
        ? cloneElement(child as ReactElement<Record<string, unknown>>, {
            id: controlId,
            "aria-describedby": describedBy,
            "aria-invalid": error ? true : undefined,
            "aria-required": required || undefined,
            ...(error && STATEFUL_CONTROLS.includes(child.type) ? { state: "error" } : {}),
          })
        : child}
      {hint && !error ? (
        <p id={hintId} className="m-0 text-xs text-fg-dim">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="m-0 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
