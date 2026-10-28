import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { brexApi, type BrexProfile } from "../lib/api";

type Props = {
  profileId: string;
  disabled: boolean;
  onDeleted: (profileId: string) => void;
};

export function BrexProfileDeleteAction({ profileId, disabled, onDeleted }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [armed, setArmed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const deleteProfile = async () => {
    if (!armed) {
      setArmed(true);
      timer.current = setTimeout(() => setArmed(false), 3000);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    setArmed(false);
    setDeleting(true);
    setError(null);
    try {
      const confirmToken = btoa(Math.random().toString()).substring(0, 16);
      await brexApi.delete(profileId, confirmToken);
      queryClient.setQueryData<BrexProfile[]>(["s1000d-brex"], (profiles) =>
        profiles?.filter((profile) => profile.id !== profileId),
      );
      queryClient.removeQueries({ queryKey: ["s1000d-brex", profileId], exact: true });
      onDeleted(profileId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div>
      <button
        type="button"
        className="btn danger small"
        disabled={disabled || deleting}
        aria-busy={deleting}
        onClick={() => void deleteProfile()}
      >
        {armed ? t("data.confirm") : t("migration.docs.delete")}
      </button>
      {error ? <div className="error" role="alert">{error}</div> : null}
    </div>
  );
}
