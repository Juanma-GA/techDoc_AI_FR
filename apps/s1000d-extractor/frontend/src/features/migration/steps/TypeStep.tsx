import { useState } from "react";
import { Button, Card, CardContent, CardHeader, CardTitle, Select } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { DM_TYPES } from "../../../components/DmrlReview";
import type { WizardState } from "../../../lib/api";
import type { MigrationWizard } from "../useMigrationWizard";

export function TypeStep({ state, wizard }: { state: WizardState; wizard: MigrationWizard }) {
  const { t } = useTranslation();
  const [edits, setEdits] = useState<Record<string, string>>({});
  const advance = () => {
    const types = Object.fromEntries(state.dms.map((dm) => [dm.dm_id, edits[dm.dm_id] ?? dm.dm_type]));
    void wizard.action("advance", { types });
  };
  return <Card>
    <CardHeader><CardTitle>{t("migration.type.title")}</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-fg-dim">{t("migration.type.help")}</p>
      {state.dms.map((dm) => <label key={dm.dm_id}
        className="flex flex-wrap items-center justify-between gap-3 border-b border-md py-3">
        <span>{dm.is_orphan ? t("migration.dm.orphan") : dm.title}</span>
        <Select value={edits[dm.dm_id] ?? dm.dm_type} options={DM_TYPES.map((value) => ({
          value, label: t(`dmType.${value}`),
        }))} onChange={(event) => setEdits((previous) => ({ ...previous, [dm.dm_id]: event.target.value }))} />
      </label>)}
    </CardContent>
    <div className="sticky bottom-0 z-10 flex justify-between gap-3 border-t border-md bg-card p-4">
      <Button type="button" variant="secondary" disabled={wizard.busy}
        onClick={() => void wizard.action("back")}>{t("common.back")}</Button>
      <Button type="button" disabled={wizard.busy} onClick={advance}>{t("migration.type.validate")}</Button>
    </div>
  </Card>;
}
