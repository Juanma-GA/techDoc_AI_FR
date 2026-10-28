import { usePatchPreparationMapping } from "../../hooks/usePreparation";
import type { Document } from "../../types/domain";
import { ClientMetadataPanel } from "../reviewer/ClientMetadataPanel";

type Props = {
  document: Document;
  mapping: Record<string, unknown>;
};

export function PreparationMetadataPanel({ document, mapping }: Props) {
  const patchMapping = usePatchPreparationMapping(document.id);

  return (
    <ClientMetadataPanel
      document={document}
      mappingValues={mapping}
      onSaveMapping={async (mapping) => {
        await patchMapping.mutateAsync({ mapping });
      }}
      titleKey="preparation.mappingTitle"
      subtitleKey="preparation.mappingSubtitle"
    />
  );
}
