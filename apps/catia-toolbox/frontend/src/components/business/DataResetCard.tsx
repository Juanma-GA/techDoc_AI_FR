import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { adminApi } from "../../lib/api";
import { useWorkspace } from "../../stores/workspace";

type Props = {
  title: string;
  description: string;
};

export function DataResetCard({ title, description }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [armed, setArmed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const resetMutation = useMutation({
    mutationFn: () => adminApi.resetAll(),
    onSuccess: (data) => {
      const deleted =
        Object.entries(data.deleted ?? {})
          .map(([key, count]) => `${key}: ${count}`)
          .join(", ") || t("data.resetEmpty");
          useWorkspace.getState().resetWorkspace();
      setNotice(t("data.resetOk", { items: deleted }));
      void queryClient.invalidateQueries();
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : String(cause)),
  });

  const disarm = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    setArmed(false);
  };

  const handleReset = () => {
    setNotice(null);
    setError(null);
    if (!armed) {
      setArmed(true);
      timerRef.current = setTimeout(disarm, 3000);
      return;
    }
    disarm();
    resetMutation.mutate();
  };

  return (
    <article className="card">
      <h2 className="card-title">{title}</h2>
      <p className="banner warn">{description}</p>
      <div className="row">
        <button
          type="button"
          className="btn danger"
          onClick={handleReset}
          disabled={resetMutation.isPending}
        >
          {resetMutation.isPending ? <span className="spinner" /> : null}
          <span>{armed ? t("common.confirmAgain") : t("data.resetAll")}</span>
        </button>
      </div>
      {notice ? <p className="success">{notice}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
    </article>
  );
}