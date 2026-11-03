import { Button, Spinner } from "@internal/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
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
      const deleted = Object.values(data.deleted ?? {}).reduce((total, count) => total + count, 0);
      useWorkspace.getState().resetWorkspace();
      setNotice(t("data.resetOk", { items: deleted || t("data.resetEmpty") }));
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
    <section className="workflow-section">
      <h2 className="section-title">{title}</h2>
      <p className="banner warn">{description}</p>
      <div className="row">
        <Button
          type="button"
          variant="danger"
          onClick={handleReset}
          disabled={resetMutation.isPending}
        >
          {resetMutation.isPending ? <Spinner aria-label={t("common.loading")} /> : <Trash2 size={16} aria-hidden="true" />}
          <span>{armed ? t("common.confirmAgain") : t("data.resetAll")}</span>
        </Button>
      </div>
      {notice ? <p className="success" role="status">{notice}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
    </section>
  );
}
