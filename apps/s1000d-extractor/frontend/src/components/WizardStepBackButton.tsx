import { Button } from "@internal/ui";
import { useTranslation } from "react-i18next";

import type { WizardStep } from "../lib/api";

type Props = {
  step: WizardStep;
  steps: readonly WizardStep[];
  disabled: boolean;
  onBack: () => void;
};

export function WizardStepBackButton({ step, steps, disabled, onBack }: Props) {
  const { t } = useTranslation();
  if (steps.indexOf(step) <= 0) return null;

  return (
    <Button
      variant="secondary"
      disabled={disabled}
      onClick={onBack}
    >
      {t("common.back")}
    </Button>
  );
}
