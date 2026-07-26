/**
 * Front-side unit helpers — used by tests and the local "manual convert"
 * affordance. The backend remains the source of truth for suggestions.
 */

export const CONVERSIONS: Record<string, { factor: number; to: string }> = {
  cm_in: { factor: 1 / 2.54, to: "in" },
  mm_in: { factor: 1 / 25.4, to: "in" },
  m_ft: { factor: 3.281, to: "ft" },
  in_cm: { factor: 2.54, to: "cm" },
  ft_m: { factor: 0.3048, to: "m" },
  kg_lb: { factor: 2.2046, to: "lb" },
  lb_kg: { factor: 0.4536, to: "kg" },
};

export function convert(value: number, from: string, target: "metric" | "imperial"): string | null {
  const map: Record<string, string> = {
    metric_in: "in_cm",
    metric_ft: "ft_m",
    metric_lb: "lb_kg",
    imperial_cm: "cm_in",
    imperial_mm: "mm_in",
    imperial_m: "m_ft",
    imperial_kg: "kg_lb",
  };
  const key = map[`${target}_${from}`];
  if (!key) return null;
  const conv = CONVERSIONS[key];
  if (!conv) return null;
  const out = value * conv.factor;
  const rounded = Math.round(out * 100) / 100;
  return `${rounded} ${conv.to}`;
}
