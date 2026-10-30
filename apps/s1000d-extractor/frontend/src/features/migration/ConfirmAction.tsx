import { useEffect, useRef, useState } from "react";
import { Button } from "@internal/ui";
import { useTranslation } from "react-i18next";

export function ConfirmAction({ label, onConfirm, disabled = false }: {
  label: string; onConfirm: () => void; disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(timer.current), []);
  return <Button type="button" variant="danger" size="sm" disabled={disabled}
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
