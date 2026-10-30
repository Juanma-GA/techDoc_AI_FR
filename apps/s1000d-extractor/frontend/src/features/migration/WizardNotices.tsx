import { Card, CardHeader } from "@internal/ui";
import { useTranslation } from "react-i18next";
import type { MigrationWizard } from "./useMigrationWizard";

export function IllustrationWarning({ count }: { count: number }) {
  const { t } = useTranslation();
  return count ? <Card role="status" aria-live="polite">
    <CardHeader>{t("migration.generate.illustrationErrors", { count })}</CardHeader>
  </Card> : null;
}
export function WizardNotices({ wizard }: { wizard: MigrationWizard }) {
  const { t } = useTranslation();
  return <>
    {wizard.error ? <p role="alert" className="text-danger">{wizard.error}</p> : null}
    {wizard.reused && !wizard.busy && !wizard.starting && !wizard.error
      ? <p role="status" className="text-info">{t("migration.ui.reused")}</p> : null}
    <IllustrationWarning count={wizard.wiz?.illustration_errors ?? 0} />
    {wizard.wiz?.resources?.errors?.map((error) => <p role="alert" key={error} className="text-danger">
      {t("migration.resource.notApplied", { detail: error })}
    </p>)}
  </>;
}
