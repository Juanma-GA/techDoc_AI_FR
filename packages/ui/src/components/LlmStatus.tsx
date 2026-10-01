export type LlmStatusLabels = {
  label: string;
  title: string;
  on: string;
  off: string;
  untested: string;
  noKey: string;
};

type LlmState = "ok" | "disabled" | "untested" | "not_configured";

const LABEL_KEY: Record<LlmState, keyof LlmStatusLabels> = {
  ok: "on",
  disabled: "off",
  untested: "untested",
  not_configured: "noKey",
};

function isLlmState(status?: string | null): status is LlmState {
  return status === "ok" || status === "disabled" || status === "untested" || status === "not_configured";
}

export type LlmStatusProps = {
  status?: string | null;
  labels: LlmStatusLabels;
};

export function LlmStatus({ status, labels }: LlmStatusProps) {
  const state = isLlmState(status) ? status : undefined;

  return (
    <div className="ui-llm-status" title={labels.title}>
      {labels.label}{" "}
      <span className="ui-llm-badge" data-status={state ?? "unknown"}>
        {state ? labels[LABEL_KEY[state]] : "?"}
      </span>
    </div>
  );
}