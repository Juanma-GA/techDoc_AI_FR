import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { PreparationChecklistStep } from "../components/preparation/PreparationChecklistStep";
import { PreparationOcrStep } from "../components/preparation/PreparationOcrStep";
import { PreparationReview } from "../components/preparation/PreparationReview";
import { PageHeader } from "../components/PageHeader";
import { DocumentMetaPanel } from "../components/reviewer/DocumentMetaPanel";
import { useDocument } from "../hooks/useDocuments";
import {
  useDetectPreparationPages,
  usePatchPreparationDecision,
  usePreparationState,
  useRunOcrDocument,
  useRunOcrPage,
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
  const runOcrPage = useRunOcrPage(id);
  const validateAllOcr = useValidateAllOcrPages(id);
  const detectPages = useDetectPreparationPages(id);
  const patchDecision = usePatchPreparationDecision(id);
  const [step, setStep] = useState<Step>(1);

  const state = preparation.data;
  const ocrComplete = Boolean(
    state &&
      state.page_count > 0 &&
      state.pages.length === state.page_count &&
      state.pages.every(
        (page) =>
          !page.needs_ocr ||
          state.ocr_results_available.some(
            (result) => result.provider === "mistral" && result.page === page.page,
          ),
      ),
  );
  const unvalidated = state?.pages.filter(
    (page) => page.needs_ocr && !state.validated_pages.includes(page.page),
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

  const checklistError = detectPages.isError
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
              : runOcrPage.isError
                ? messageOf(runOcrPage.error)
              : detectPages.isError
                ? t("preparation.detectFailed", { message: messageOf(detectPages.error) })
                : null
          }
          onRunOcrAll={() => runOcrDocument.mutate()}
          runningOcrAll={runOcrDocument.isPending}
          onRunOcrPage={(page) => runOcrPage.mutate({ page, provider: "mistral" })}
          runningOcrPage={runOcrPage.isPending}
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
          detecting={detectPages.isPending}
          savingDecision={patchDecision.isPending}
          onDetect={() => detectPages.mutate()}
          onDecision={(page, isModified) => patchDecision.mutate({ page, is_modified: isModified })}
          onContinue={() => setStep(3)}
        />
      ) : null}

      {step === 3 ? (
        <>
          <DocumentMetaPanel document={document.data} />
          <PreparationReview document={document.data} preparation={state} />
        </>
      ) : null}
    </div>
  );
}
