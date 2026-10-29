import { useTranslation } from "react-i18next";

import {
  Card,
  DemoModeSelector,
  Spinner,
  useDemoMode,
  type DemoMode,
} from "@internal/ui";

type SettingsToolProps = {
  pending: boolean;
  loadError: boolean;
  onModeChange: (mode: DemoMode) => void;
};

export function SettingsTool({ pending, loadError, onModeChange }: SettingsToolProps) {
  const { t } = useTranslation();
  const { mode, isReady } = useDemoMode();

  return (
    <Card className="panel">
      <div className="panel-heading">
        <div>
          <h2>{t("settings.demo.title")}</h2>
          <p>{t("settings.demo.hint")}</p>
        </div>
      </div>
      <DemoModeSelector
        mode={mode}
        labels={{
          normal: t("settings.demo.normal"),
          demo: t("settings.demo.demo"),
        }}
        ariaLabel={t("settings.demo.title")}
        disabled={!isReady || pending}
        onModeChange={onModeChange}
      />
      {pending ? (
        <p className="preview-status" role="status">
          <Spinner aria-label={t("common.loading")} />
          {t("settings.demo.loading")}
        </p>
      ) : null}
      {loadError ? (
        <p className="feedback feedback-error" role="alert">
          {t("settings.demo.loadError")}
        </p>
      ) : null}
    </Card>
  );
}
