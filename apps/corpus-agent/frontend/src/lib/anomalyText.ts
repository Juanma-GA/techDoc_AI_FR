import type { TFunction } from "i18next";

/**
 * Résout le texte d'une anomalie comme le preview (tAnomalyText) : si une clé
 * i18n existe et est traduite, on substitue les params {param} ; sinon on
 * retombe sur le texte brut FR du backend.
 */
export function resolveAnomalyText(
  t: TFunction,
  raw: string,
  key: string | null,
  paramsJson: string | null,
): string {
  if (!key) return raw;
  const tpl = t(key);
  if (!tpl || tpl === key) return raw;
  let params: Record<string, unknown> = {};
  if (paramsJson) {
    try {
      params = JSON.parse(paramsJson) as Record<string, unknown>;
    } catch {
      /* garde {} */
    }
  }
  return tpl.replace(/\{(\w+)\}/g, (_m, name: string) =>
    name in params ? String(params[name]) : `{${name}}`,
  );
}
