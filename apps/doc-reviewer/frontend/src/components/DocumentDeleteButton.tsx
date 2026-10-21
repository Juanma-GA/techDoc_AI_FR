import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

type Props = {
  label: string;
  ariaLabel: string;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
};

export function DocumentDeleteButton({
  label,
  ariaLabel,
  confirmLabel,
  onConfirm,
  disabled = false,
}: Props) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timeout = window.setTimeout(() => setArmed(false), 3000);
    return () => window.clearTimeout(timeout);
  }, [armed]);

  return (
    <button
      type="button"
      className="btn small danger"
      disabled={disabled}
      aria-label={armed ? confirmLabel : ariaLabel}
      title={armed ? confirmLabel : ariaLabel}
      onClick={(event) => {
        event.stopPropagation();
        if (armed) {
          setArmed(false);
          onConfirm();
        } else {
          setArmed(true);
        }
      }}
    >
      <Trash2 size={14} aria-hidden="true" />
      <span aria-live="polite">{armed ? confirmLabel : label}</span>
    </button>
  );
}
