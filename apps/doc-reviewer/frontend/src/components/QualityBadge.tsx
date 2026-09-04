import { useTranslation } from "react-i18next";

import type { QualityState } from "../types/domain";

type Props = {
  state: QualityState;
  coverage?: number;
  engine?: string;
};

// Reutilise le skin `.badge.*` tokenise (memes couleurs que le reste de l'app,
// aucun hex en dur — cf. regle #4). vert=ok / orange=warn / rouge=danger.
const STATE_CLASS: Record<QualityState, string> = {
  analyzable: "ok",
  degraded: "warn",
  unusable: "danger",
};

/**
 * Badge de revuabilite (portail qualite). Homogene tous formats : indique si un
 * document (PDF natif ou Word converti) est réellement analysable, dégradé, ou
 * non exploitable (scanné sans couche texte -> revue non fiable).
 */
export function QualityBadge({ state, coverage, engine }: Props) {
  const { t } = useTranslation();
  const cls = STATE_CLASS[state] ?? "ok";
  const title = [
    t(`quality.${state}.hint`),
    typeof coverage === "number" ? t("quality.coverage", { pct: coverage }) : null,
    engine ? t("quality.engine", { engine }) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <span className={`badge ${cls}`} title={title}>
      {t(`quality.${state}.label`)}
      {typeof coverage === "number" && state !== "analyzable" ? ` · ${coverage}%` : ""}
    </span>
  );
}
