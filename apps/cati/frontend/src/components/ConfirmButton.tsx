import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, type ButtonProps } from "@internal/ui";

type Props = {
  onConfirm: () => void;
  label: string;
  confirmLabel?: string;
  variant?: ButtonProps["variant"];
  size?: ButtonProps["size"];
  disabled?: boolean;
};

/**
 * Confirmation d'action destructrice par double-clic (standard) : 1er clic arme
 * le bouton, 2e clic dans les 3 s execute. Jamais de dialogue natif navigateur.
 */
export function ConfirmButton({ onConfirm, label, confirmLabel, variant = "danger", size = "sm", disabled }: Props) {
  const { t } = useTranslation();
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timer.current), []);

  const handleClick = () => {
    if (armed) {
      clearTimeout(timer.current);
      setArmed(false);
      onConfirm();
      return;
    }
    setArmed(true);
    timer.current = setTimeout(() => setArmed(false), 3000);
  };

  return (
    <Button type="button" variant={armed ? "danger" : variant} size={size} disabled={disabled} onClick={handleClick}>
      {armed ? (confirmLabel ?? t("common.confirm")) : label}
    </Button>
  );
}
