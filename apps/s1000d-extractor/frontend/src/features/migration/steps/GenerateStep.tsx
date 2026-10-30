import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, Checkbox, buttonVariants, Button, Spinner } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { BrexAnalysisSummary } from "../../../components/BrexAnalysisSummary";
import { WizardZipDownloadButton } from "../../../components/WizardZipDownloadButton";
import { WizardStepBackButton } from "../../../components/WizardStepBackButton";
import { getCommonMissingFields } from "../../../lib/migrationUtils";
import { resourcesApi, wizardApi, type WizardDm, type WizardState } from "../../../lib/api";
import type { MigrationWizard } from "../useMigrationWizard";
import { ImageGallery } from "../ImageGallery";
import { GeneratedDmRow } from "./GeneratedDmRow";

export function generationHasError(dm: WizardDm): boolean {
  return !dm.has_xml || dm.xsd_valid === false ||
    (dm.brex_violations ?? []).some((violation) => violation.severity === "error");
}
export function GenerateStep({ state, wizard, docId, profileId }: {
  state: WizardState; wizard: MigrationWizard; docId: string; profileId: string | null;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [errorsOnly, setErrorsOnly] = useState(false);
  const images = useQuery({ queryKey: ["s1000d-images", docId], queryFn: () => wizardApi.images(docId) });
  const common = useMemo(() => getCommonMissingFields(state.dms), [state.dms]);
  const commonSet = useMemo(() => new Set(common), [common]);
  const errors = state.dms.filter((dm) => dm.xsd_valid === false).length;
  const valid = state.dms.filter((dm) => !generationHasError(dm) && dm.xsd_valid === true &&
    !dm.missing_fields?.length && !dm.cir_unresolved?.length).length;
  const visible = errorsOnly ? state.dms.filter(generationHasError) : state.dms;
  return <Card>
    <CardHeader><CardTitle>{t("migration.generate.title", { count: state.dms.length })}</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p role="status">{t("migration.ui.summary", { valid, incomplete: state.dms.length - valid - errors, errors })}</p>
      <div className="flex flex-wrap items-end gap-3">
        <WizardStepBackButton steps={state.steps ?? []} step={state.step} disabled={wizard.busy}
          onBack={() => void wizard.action("back")} />
        {state.resources?.dmrl_count ? <a className={buttonVariants({ variant: "secondary" })}
          href={resourcesApi.pmcUrl(docId)}>{t("migration.generate.pmc")}</a> : null}
        {state.dms.some((dm) => dm.has_xml) ? <Button type="button" variant="secondary"
          onClick={() => navigate("/validation", { state: { generated: {
            documentId: docId, dmIds: state.dms.filter((dm) => dm.has_xml).map((dm) => dm.dm_id),
          } } })}>{t("migration.generate.validate")}</Button> : null}
        <WizardZipDownloadButton docId={docId}
          disabled={wizard.busy || !state.dms.length || state.dms.some((dm) => !dm.has_xml)} />
      </div>
      <BrexAnalysisSummary hasProfile={state.has_brex_profile === true} profileId={profileId} dms={state.dms} />
      <label className="flex items-center gap-2">
        <Checkbox checked={errorsOnly} onCheckedChange={setErrorsOnly} />
        {t("migration.ui.errorsOnly")}
      </label>
      {common.length ? <details className="text-warning">
        <summary>{t("migration.generate.commonMissingFields")}</summary>
        <ul>{common.map((field) => <li className="break-all" key={field}>{field}</li>)}</ul>
      </details> : null}
      {visible.map((dm) => <GeneratedDmRow key={dm.dm_id} dm={dm} docId={docId}
        commonFields={commonSet} hasBrex={state.has_brex_profile === true} />)}
      {images.error ? <p role="alert" className="text-danger">{images.error.message}</p> : null}
      {images.isLoading ? <Spinner aria-label={t("common.loading")} /> : null}
      <ImageGallery docId={docId} names={images.data ?? []} />
    </CardContent>
  </Card>;
}
