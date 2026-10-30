import { useState } from "react";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Checkbox, Input, Select } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { DmPreview } from "../../../components/DmPreview";
import { WizardStepBackButton } from "../../../components/WizardStepBackButton";
import { ConfirmAction } from "../ConfirmAction";
import type { MigrationWizard } from "../useMigrationWizard";
import type { WizardState } from "../../../lib/api";

export function SplitStep({ state, wizard }: { state: WizardState; wizard: MigrationWizard }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [titleEdits, setTitleEdits] = useState<Record<string, string>>({});
  const [level, setLevel] = useState(state.split_level);
  const [message, setMessage] = useState<string | null>(null);
  const update = async (params: Record<string, unknown>) => {
    if (await wizard.action("update", params)) setSelected(new Set());
  };
  return <Card>
    <CardHeader><CardTitle>{t("migration.split.title", { count: state.dms.length })}</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-fg-dim">{t("migration.analysis.help")}</p>
      {state.dmrl_dm_count ? <p>{t("migration.split.dmrlDriven", { count: state.dmrl_dm_count })}</p> : null}
      <WizardStepBackButton steps={state.steps ?? []} step={state.step} disabled={wizard.busy}
        onBack={() => void wizard.action("back")} />
      <details className="space-y-3">
        <summary>{t("migration.split.review", { count: state.dms.length })}</summary>
        <div className="flex flex-wrap items-end gap-3 py-3">
          <label><span className="block">{t("migration.split.level")}</span>
            <Select value={level} onChange={(event) => setLevel(event.target.value)} options={[
              { value: "chapter", label: t("migration.split.levelChapter") },
              { value: "section", label: t("migration.split.levelSection") },
              { value: "subsection", label: t("migration.split.levelSubsection") },
            ]} />
          </label>
          <Button type="button" variant="secondary" disabled={wizard.busy}
            onClick={() => void update({ split_level: level })}>{t("migration.split.reanalyze")}</Button>
          <Button type="button" variant="secondary" disabled={wizard.busy} onClick={() => {
            if (selected.size < 2) setMessage(t("migration.split.needTwo"));
            else { setMessage(null); void update({ op: "merge", ids: [...selected] }); }
          }}>{t("migration.split.merge")}</Button>
          <Button type="button" variant="secondary" disabled={wizard.busy}
            onClick={() => void update({ op: "hide_zones", zones: ["header", "footer"] })}>
            {t("migration.split.hideZones")}
          </Button>
          <Button type="button" variant="ghost" disabled={wizard.busy || !state.can_undo}
            onClick={() => void update({ op: "undo" })}>{t("migration.split.undo")}</Button>
        </div>
        {message ? <p role="alert" className="text-danger">{message}</p> : null}
        <p className="text-sm text-fg-dim">{t("migration.split.help")}</p>
        {state.dms.map((dm) => <div key={dm.dm_id} className="space-y-3 border-b border-md py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Checkbox checked={selected.has(dm.dm_id)} aria-label={t("migration.ui.selectDm", { title: dm.title })}
              onCheckedChange={(checked) => setSelected((previous) => {
                const next = new Set(previous);
                if (checked) next.add(dm.dm_id); else next.delete(dm.dm_id);
                return next;
              })} />
            <Input className="grow" aria-label={t("migration.ui.dmTitle", { title: dm.title })}
              value={titleEdits[dm.dm_id] ?? (dm.is_orphan ? t("migration.dm.orphan") : dm.title)}
              onChange={(event) => setTitleEdits((previous) => ({ ...previous, [dm.dm_id]: event.target.value }))} />
            <Badge variant="info">{t(`dmType.${dm.dm_type}`)}</Badge>
            <span className="text-sm text-fg-dim">{dm.node_count}</span>
            <Button type="button" variant="ghost" size="sm" disabled={wizard.busy}
              onClick={() => void update({ op: "rename", id: dm.dm_id, title: titleEdits[dm.dm_id] ?? dm.title })}>
              {t("migration.split.rename")}
            </Button>
            <Button type="button" variant="ghost" size="sm" disabled={wizard.busy}
              onClick={() => void update({ op: "split", id: dm.dm_id })}>{t("migration.split.split")}</Button>
            <ConfirmAction label={t("migration.split.exclude")} disabled={wizard.busy}
              onConfirm={() => void update({ op: "exclude", id: dm.dm_id })} />
          </div>
          <DmPreview preview={dm.preview} />
        </div>)}
      </details>
      <div className="flex justify-end">
        <Button type="button" disabled={wizard.busy} onClick={() => void wizard.validateAndGenerate()}>
          {t(wizard.busy ? "migration.analysis.processing" : "migration.analysis.validate")}
        </Button>
      </div>
    </CardContent>
  </Card>;
}
