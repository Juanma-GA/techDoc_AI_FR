import { useEffect, useRef, useState } from "react";
import { Button, type ButtonProps } from "@internal/ui";
import { useTranslation } from "react-i18next";

type ConfirmButtonProps = {
  label: string;
  confirmLabel?: string;
  onConfirm: () => void;
  size?: NonNullable<ButtonProps["size"]>;
  disabled?: boolean;
  variant?: NonNullable<ButtonProps["variant"]>;
};

export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  size = "md",
  disabled = false,
  variant = "danger",
}: ConfirmButtonProps) {
  const { t } = useTranslation();
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current !== null) clearTimeout(timer.current);
  }, []);

  useEffect(() => {
    if (disabled && timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
      setArmed(false);
    }
  }, [disabled]);

  const handleClick = () => {
    if (!armed) {
      setArmed(true);
      timer.current = setTimeout(() => {
        timer.current = null;
        setArmed(false);
      }, 3000);
      return;
    }
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    setArmed(false);
    onConfirm();
  };

  return (
    <Button
      type="button"
      variant={armed ? "danger" : variant}
      size={size}
      disabled={disabled}
      aria-live="polite"
      onClick={handleClick}
    >
      {armed ? confirmLabel ?? t("common.confirmAgain") : label}
    </Button>
  );
}
