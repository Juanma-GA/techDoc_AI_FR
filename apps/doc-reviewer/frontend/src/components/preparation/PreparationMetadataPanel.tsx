import { useTranslation } from "react-i18next";

import { usePatchPreparationMapping, usePreparationState } from "../../hooks/usePreparation";
import type { Document } from "../../types/domain";
import { ClientMetadataPanel } from "../reviewer/ClientMetadataPanel";

type Props = {
  document: Document;
};

export function PreparationMetadataPanel({ document }: Props) {
  const { t } = useTranslation();
  const preparation = usePreparationState(document.id);
  const patchMapping = usePatchPreparationMapping(document.id);

  if (preparation.isLoading) {
    return <p className="hint">{t("common.loading")}</p>;
  }
  if (preparation.isError || !preparation.data) {
    const message = preparation.error instanceof Error
      ? preparation.error.message
      : t("common.retry");
    return <p className="banner warn" role="alert">{message}</p>;
  }

  return (
    <ClientMetadataPanel
      document={document}
      mappingValues={preparation.data.preparation_mapping}
      onSaveMapping={async (mapping) => {
        await patchMapping.mutateAsync({ mapping });
      }}
      titleKey="preparation.mappingTitle"
      subtitleKey="preparation.mappingSubtitle"
    />
  );
}
