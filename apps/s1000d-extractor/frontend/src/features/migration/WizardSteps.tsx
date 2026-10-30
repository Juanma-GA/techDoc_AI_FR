import { useState } from "react";
import { PreliminaryReview } from "../../components/business/PreliminaryReview";
import { DmrlReview } from "../../components/DmrlReview";
import { SplitStep } from "./steps/SplitStep";
import { TypeStep } from "./steps/TypeStep";
import { StructureStep } from "./steps/StructureStep";
import { GenerateStep } from "./steps/GenerateStep";
import type { WizardState } from "../../lib/api";
import type { MigrationWizard } from "./useMigrationWizard";

function DmrlStep({ state, wizard }: { state: WizardState; wizard: MigrationWizard }) {
  const [edits, setEdits] = useState<Record<number, string>>({});
  return <DmrlReview rows={state.dmrl ?? []}
    dmCount={state.dmrl_dm_count ?? (state.dmrl ?? []).filter((row) => !row.is_pm_title).length}
    busy={wizard.busy} edits={edits}
    onTitleChange={(index, title) => setEdits((previous) => ({ ...previous, [index]: title }))}
    onUpdate={(params) => void wizard.action("update", params)}
    onAdvance={() => void wizard.action("advance", {})} />;
}
export function WizardSteps({ wizard, profileId }: { wizard: MigrationWizard; profileId: string | null }) {
  const state = wizard.wiz;
  if (!state || !wizard.docId) return null;
  switch (state.step) {
    case "dmrl": return <DmrlStep state={state} wizard={wizard} />;
    case "split": return <SplitStep state={state} wizard={wizard} />;
    case "type": return <TypeStep state={state} wizard={wizard} />;
    case "structure": return <StructureStep state={state} wizard={wizard} />;
    case "preliminary": return state.preliminary ? <PreliminaryReview key={wizard.docId}
      docId={wizard.docId} initial={state.preliminary} dms={state.dms} busy={wizard.busy}
      onBack={() => void wizard.action("back")} onGenerate={() => void wizard.action("advance", {})}
      onFlushReady={wizard.onFlushReady} /> : null;
    case "generate": return <GenerateStep state={state} wizard={wizard} docId={wizard.docId} profileId={profileId} />;
  }
}
