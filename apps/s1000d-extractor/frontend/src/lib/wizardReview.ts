import type { WizardState } from "./api";

export function hasUnmatchedDmrlDms(state: WizardState): boolean {
  return (
    state.step === "dmrl" &&
    (state.dmrl ?? []).some((row) => !row.is_pm_title && !row.matched)
  );
}

export function hasUnresolvedDmrlTypeIssues(state: WizardState): boolean {
  return (
    state.step === "dmrl" &&
    (state.dmrl ?? []).some(
      (row) =>
        !row.is_pm_title &&
        Boolean(row.type_conflict || row.type_issue) &&
        !row.dm_type,
    )
  );
}

export function hasDmrlTypeWarnings(state: WizardState): boolean {
  return (
    state.step === "dmrl" &&
    (state.dmrl ?? []).some(
      (row) => !row.is_pm_title && Boolean(row.type_conflict || row.type_issue),
    )
  );
}

export function needsDmrlReview(state: WizardState): boolean {
  return hasUnmatchedDmrlDms(state) || hasDmrlTypeWarnings(state);
}
