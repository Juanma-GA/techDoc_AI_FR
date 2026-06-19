import { useHealth } from "../hooks/useHealth";

// Indicateur LLM du sidebar (.llm-status + .badge), regle CLAUDE.md #13.
// Le vert (ON) n'apparait que si cle effective + test reussi + interrupteur ON.
const BADGE_CLASS: Record<string, string> = {
  ok: "badge ok",
  disabled: "badge off",
  untested: "badge warn",
  not_configured: "badge warn",
};
const LABEL: Record<string, string> = {
  ok: "ON",
  disabled: "OFF",
  untested: "A TESTER",
  not_configured: "NO KEY",
};

export function LlmBadge() {
  const { data } = useHealth();
  const status = data?.llm;
  const badgeClass = status ? (BADGE_CLASS[status] ?? "badge warn") : "badge off";
  const label = status ? (LABEL[status] ?? "?") : "?";

  return (
    <div className="llm-status" title="Etat du LLM (voir Parametres)">
      LLM <span className={badgeClass}>{label}</span>
    </div>
  );
}
