import { useEffect, useMemo, useState } from "react";
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
  useOcrProviders,
  usePatchPageReadability,
  usePatchPreparationDecision,
  usePreparationState,
  useRunOcrPage,
  useSelectOcrProvider,
  useValidateOcrPage,
} from "../hooks/usePreparation";
import type { OcrProvider } from "../types/preparation";

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
  const providers = useOcrProviders(id);
  const selectProvider = useSelectOcrProvider(id);
  const patchReadability = usePatchPageReadability(id);
  const runOcr = useRunOcrPage(id);
  const validateOcr = useValidateOcrPage(id);
  const importChecklist = useImportPreparationChecklist(id);
  const detectPages = useDetectPreparationPages(id);
  const patchDecision = usePatchPreparationDecision(id);
  const [step, setStep] = useState<Step>(1);

  const state = preparation.data;
  const needsOcr = useMemo(
    () => state?.pages.filter((page) => page.needs_ocr) ?? [],
    [state?.pages],
  );
  const unvalidated = needsOcr.filter(
    (page) => !state?.validated_pages.includes(page.page),
  );
  const canContinueToChecklist = Boolean(
    state &&
    state.page_count > 0 &&
      (needsOcr.length === 0 ||
        (state.selected_provider && unvalidated.length === 0)),
  );
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
  if (document.isLoading || preparation.isLoading || providers.isLoading) {
    return <p className="empty-state">{t("common.loading")}</p>;
  }
  if (document.isError || !document.data || preparation.isError || providers.isError || !state) {
    const error = document.error ?? preparation.error ?? providers.error;
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
          providers={providers.data ?? []}
          error={runOcr.isError ? messageOf(runOcr.error) : null}
          onSetProvider={(provider: OcrProvider) => selectProvider.mutate({ provider })}
          selectingProvider={selectProvider.isPending}
          onSetNeedsOcr={(page, needsOcrValue) =>
            patchReadability.mutate({ page, needs_ocr: needsOcrValue })
          }
          updatingReadability={patchReadability.isPending}
          onRunOcr={(page, provider) => runOcr.mutate({ page, provider })}
          runningOcr={runOcr.isPending}
          onValidate={(page, provider, validated) =>
            validateOcr.mutate({ page, provider, validated })
          }
          validating={validateOcr.isPending}
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
