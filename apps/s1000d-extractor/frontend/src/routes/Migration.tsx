import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@internal/ui";
import { PdfCutStartSelector } from "../components/PdfCutStartSelector";
import { UploadCard } from "../features/migration/UploadCard";
import { DocumentList } from "../features/migration/DocumentList";
import { WizardSteps } from "../features/migration/WizardSteps";
import { WizardNotices } from "../features/migration/WizardNotices";
import { useMigrationInputs } from "../features/migration/useMigrationInputs";
import { useMigrationWizard } from "../features/migration/useMigrationWizard";

export function Migration() {
  const { t } = useTranslation();
  const inputs = useMigrationInputs();
  const wizard = useMigrationWizard(inputs);
  const anchor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (wizard.wiz?.step) anchor.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [wizard.wiz?.step]);
  return <div className="space-y-5">
    <PageHeader title={t("migration.title")} description={t("migration.subtitle")} />
    <UploadCard inputs={inputs} wizard={wizard} />
    {wizard.pdfCut ? <PdfCutStartSelector
      docId={wizard.pdfCut.docId} detection={wizard.pdfCut.detection}
      selectedTitle={wizard.pdfCut.selectedTitle} startPage={wizard.pdfCut.startPage}
      endPage={wizard.pdfCut.endPage} busy={wizard.pdfCutBusy}
      onTitleChange={(selectedTitle) => wizard.setPdfCut((current) => current ? { ...current, selectedTitle } : current)}
      onStartPageChange={(startPage) => wizard.setPdfCut((current) => current ? { ...current, startPage } : current)}
      onEndPageChange={(endPage) => wizard.setPdfCut((current) => current ? { ...current, endPage } : current)}
      onDetect={(title) => void wizard.redetect(title)} onConfirm={() => void wizard.confirmPdfCut()}
    /> : null}
    <DocumentList inputs={inputs} wizard={wizard} />
    <div ref={anchor} className="space-y-4">
      <WizardNotices wizard={wizard} />
      <WizardSteps key={`${wizard.docId}:${wizard.wiz?.step}`} wizard={wizard} profileId={inputs.brexId} />
    </div>
  </div>;
}
