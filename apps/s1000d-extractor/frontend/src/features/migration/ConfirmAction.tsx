import { useEffect, useRef, useState } from "react";
import { Button } from "@internal/ui";
import { useTranslation } from "react-i18next";

export function ConfirmAction({ label, onConfirm, disabled = false, variant = "danger" }: {
  label: string; onConfirm: () => void; disabled?: boolean; variant?: "danger" | "ghost" | "secondary";
}) {
  const { t } = useTranslation();
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(timer.current), []);
  return <Button type="button" variant={armed ? "danger" : variant} size="sm" disabled={disabled}
    aria-live="polite" onClick={() => {
      if (!armed) {
        setArmed(true);
        timer.current = setTimeout(() => setArmed(false), 3000);
      } else {
        clearTimeout(timer.current);
        setArmed(false);
        onConfirm();
      }
    }}>{armed ? t("common.confirmAgain") : label}</Button>;
}
