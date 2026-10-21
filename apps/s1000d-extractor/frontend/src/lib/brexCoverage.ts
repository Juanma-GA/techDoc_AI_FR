import type { BrexProfileDetail } from "./api";

export type BrexRuleCoverage = {
  total: number;
  automatic: number;
  contextual: number;
  unsupported: number;
};

export function getBrexRuleCoverage(profile: BrexProfileDetail): BrexRuleCoverage {
  const automatic = profile.rules.filter(
    (rule) => rule.support_status === "automatic",
  ).length;
  const contextual = profile.rules.filter(
    (rule) => rule.support_status === "contextual",
  ).length;
  const unsupported = profile.rules.filter(
    (rule) => rule.support_status === "unsupported",
  ).length + profile.unsupported_rules.length;

  return {
    total: profile.rules.length + profile.unsupported_rules.length,
    automatic,
    contextual,
    unsupported,
  };
}
