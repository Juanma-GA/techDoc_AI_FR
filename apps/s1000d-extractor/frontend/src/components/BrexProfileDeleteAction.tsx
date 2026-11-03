import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { brexApi, type BrexProfile } from "../lib/api";
import { createConfirmToken } from "../lib/confirmToken";
import { formatApiError } from "../lib/migrationUtils";
import { ConfirmButton } from "./ConfirmButton";

type Props = {
  profileId: string;
  disabled: boolean;
  onDeleted: (profileId: string) => void;
};

export function BrexProfileDeleteAction({ profileId, disabled, onDeleted }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteProfile = async () => {
    setDeleting(true);
    setError(null);
    try {
      await brexApi.delete(profileId, createConfirmToken());
      queryClient.setQueryData<BrexProfile[]>(["s1000d-brex"], (profiles) =>
        profiles?.filter((profile) => profile.id !== profileId),
      );
      queryClient.removeQueries({ queryKey: ["s1000d-brex", profileId], exact: true });
      onDeleted(profileId);
    } catch (caught) {
      setError(formatApiError(t, caught));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div aria-busy={deleting}>
      <ConfirmButton
        label={t("migration.docs.delete")}
        size="sm"
        disabled={disabled || deleting}
        onConfirm={() => void deleteProfile()}
      />
      {error ? <div className="text-sm text-danger" role="alert">{error}</div> : null}
    </div>
  );
}
