import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { PreparationChecklistStep } from "../components/preparation/PreparationChecklistStep";
import { PreparationOcrStep } from "../components/preparation/PreparationOcrStep";
import { PreparationReview } from "../components/preparation/PreparationReview";
import { PageHeader } from "../components/PageHeader";
import { useDocument } from "../hooks/useDocuments";
import {
  useDetectPreparationPages,
  useImportPreparationChecklist,
  usePatchPreparationDecision,
  usePreparationState,
  useRunOcrDocument,
  useValidateAllOcrPages,
} from "../hooks/usePreparation";

type Step = 1 | 2 | 3;

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

export function PreparationWorkspace() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();
  const document = useDocument(id);
  const preparation = usePreparationState(id);
  const runOcrDocument = useRunOcrDocument(id);
  const validateAllOcr = useValidateAllOcrPages(id);
  const importChecklist = useImportPreparationChecklist(id);
  const detectPages = useDetectPreparationPages(id);
  const patchDecision = usePatchPreparationDecision(id);
  const [step, setStep] = useState<Step>(1);

  const state = preparation.data;
  const ocrComplete = Boolean(
    state &&
      state.page_count > 0 &&
      state.pages.length === state.page_count &&
      state.pages.every((page) =>
        state.ocr_results_available.some(
          (result) => result.provider === "mistral" && result.page === page.page,
        ),
      ),
  );
  const unvalidated = state?.pages.filter(
    (page) => !state.validated_pages.includes(page.page),
  ) ?? [];
  const canContinueToChecklist = ocrComplete && unvalidated.length === 0;
  const decisions = state?.page_decisions ?? [];
  const hasUnknown = decisions.some((decision) => decision.is_modified === null);
  const canContinueToReview =
    decisions.length > 0 &&
    !hasUnknown &&
    decisions.some((decision) => decision.is_modified === true);

  useEffect(() => {
    if (!canContinueToChecklist && step > 1) setStep(1);
    else if (!canContinueToReview && step > 2) setStep(2);
  }, [canContinueToChecklist, canContinueToReview, step]);

  if (!id) return null;
  if (document.isLoading || preparation.isLoading) {
    return <p className="empty-state">{t("common.loading")}</p>;
  }
  if (document.isError || !document.data || preparation.isError || !state) {
    const error = document.error ?? preparation.error;
    return (
      <section className="card">
        <p className="banner warn" role="alert">{messageOf(error) || t("common.retry")}</p>
        <button type="button" className="btn secondary small" onClick={() => navigate("/preparation")}>
          {t("preparation.back")}
        </button>
      </section>
    );
  }

  const checklistError = importChecklist.isError
    ? t("preparation.checklistFailed", { message: messageOf(importChecklist.error) })
    : detectPages.isError
      ? t("preparation.detectFailed", { message: messageOf(detectPages.error) })
      : patchDecision.isError
        ? messageOf(patchDecision.error)
        : null;

  return (
    <div>
      <PageHeader
        title={t("preparation.title")}
        subtitle={document.data.original_filename}
      />
      <nav className="preparation-steps" aria-label={t("nav.preparation")}>
        <button
          type="button"
          className="preparation-step"
          aria-current={step === 1 ? "step" : undefined}
          onClick={() => setStep(1)}
        >
          {t("preparation.steps.ocr")}
        </button>
        <button
          type="button"
          className="preparation-step"
          aria-current={step === 2 ? "step" : undefined}
          disabled={!canContinueToChecklist}
          onClick={() => setStep(2)}
        >
          {t("preparation.steps.checklist")}
        </button>
        <button
          type="button"
          className="preparation-step"
          aria-current={step === 3 ? "step" : undefined}
          disabled={!canContinueToReview}
          onClick={() => setStep(3)}
        >
          {t("preparation.steps.review")}
        </button>
      </nav>

      {step === 1 ? (
        <PreparationOcrStep
          documentId={id}
          state={state}
          error={
            runOcrDocument.isError
              ? messageOf(runOcrDocument.error)
              : detectPages.isError
                ? t("preparation.detectFailed", { message: messageOf(detectPages.error) })
                : null
          }
          onRunOcrAll={() => runOcrDocument.mutate()}
          runningOcrAll={runOcrDocument.isPending}
          onValidateAllAndAnalyze={() =>
            validateAllOcr.mutate(undefined, {
              onSuccess: () => detectPages.mutate(undefined, { onSuccess: () => setStep(2) }),
            })
          }
          validatingAll={validateAllOcr.isPending}
          analyzing={detectPages.isPending}
        />
      ) : null}

      {step === 2 ? (
        <PreparationChecklistStep
          state={state}
          error={checklistError}
          importMessage={
            importChecklist.data
              ? t("preparation.checklistImported", {
                  count: importChecklist.data.imported,
                  unsupported: importChecklist.data.unsupported,
                })
              : null
          }
          importing={importChecklist.isPending}
          detecting={detectPages.isPending}
          savingDecision={patchDecision.isPending}
          onImport={(file) => importChecklist.mutate(file)}
          onDetect={() => detectPages.mutate()}
          onDecision={(page, isModified) => patchDecision.mutate({ page, is_modified: isModified })}
          onContinue={() => setStep(3)}
        />
      ) : null}

      {step === 3 ? (
        <PreparationReview document={document.data} preparation={state} />
      ) : null}
    </div>
  );
}
