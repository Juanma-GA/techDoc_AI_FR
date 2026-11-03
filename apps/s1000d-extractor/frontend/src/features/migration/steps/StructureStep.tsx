import { useCallback, useMemo, useState } from "react";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useTranslation } from "react-i18next";
import type { TreeNode, WizardState } from "../../../lib/api";
import type { MigrationWizard } from "../useMigrationWizard";
import { WizNode, type OverrideHandler } from "./WizNode";

function nodeKeys(dmId: string, nodes: TreeNode[]): string[] {
  return nodes.flatMap((node) => [`${dmId}|${node.id}`, ...nodeKeys(dmId, node.children)]);
}
function Tree({ dmId, nodes, open, onToggle, overrides, onOverride }: {
  dmId: string; nodes: TreeNode[]; open: Set<string>; onToggle: (key: string, expanded: boolean) => void;
  overrides: Record<string, string>; onOverride: OverrideHandler;
}) {
  return <ul className="space-y-1 border-l border-md pl-4">{nodes.map((node) => {
    const key = `${dmId}|${node.id}`;
    const row = <WizNode dmId={dmId} node={node} override={overrides[key]} onOverride={onOverride} />;
    return <li key={node.id}>{node.children.length ? <details open={open.has(key)}
      onToggle={(event) => {
        if (event.currentTarget.open !== open.has(key)) onToggle(key, event.currentTarget.open);
      }}>
      <summary>{row}</summary>
      {open.has(key) ? <Tree dmId={dmId} nodes={node.children} open={open} onToggle={onToggle}
        overrides={overrides} onOverride={onOverride} /> : null}
    </details> : row}</li>;
  })}</ul>;
}
export function StructureStep({ state, wizard }: {
  state: WizardState; wizard: Pick<MigrationWizard, "busy" | "action">;
}) {
  const { t } = useTranslation();
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const keys = useMemo(() => state.dms.flatMap((dm) => nodeKeys(dm.dm_id, dm.tree?.children ?? [])), [state.dms]);
  const [open, setOpen] = useState(() => new Set(keys.length > 500 ? [] : keys));
  const [activeDm, setActiveDm] = useState(state.dms[0]?.dm_id);
  const onOverride = useCallback<OverrideHandler>((dmId, nodeId, element) => {
    setOverrides((previous) => ({ ...previous, [`${dmId}|${nodeId}`]: element }));
  }, []);
  const onToggle = useCallback((key: string, expanded: boolean) => setOpen((previous) => {
    const next = new Set(previous);
    if (expanded) next.add(key); else next.delete(key);
    return next;
  }), []);
  const advance = () => void wizard.action("advance", {
    overrides: Object.entries(overrides).map(([key, element]) => {
      const [dm_id, node_id] = key.split("|");
      return { dm_id, node_id, element };
    }),
  });
  return <div className="space-y-4">
    <div className="flex flex-wrap gap-2">
      <Button type="button" variant="secondary" onClick={() => setOpen(new Set(keys))}>
        {t("migration.ui.expandAll")}
      </Button>
      <Button type="button" variant="ghost" onClick={() => setOpen(new Set())}>
        {t("migration.ui.collapseAll")}
      </Button>
    </div>
    {state.dms.map((dm) => <Card key={dm.dm_id} className="[content-visibility:auto]">
      <details open={activeDm === dm.dm_id} onToggle={(event) => {
        if (event.currentTarget.open && activeDm !== dm.dm_id) setActiveDm(dm.dm_id);
        else if (!event.currentTarget.open && activeDm === dm.dm_id) setActiveDm(undefined);
      }}>
        <summary><CardHeader><CardTitle>{dm.is_orphan ? t("migration.dm.orphan") : dm.title}{" "}
          <Badge variant="info">{t(`dmType.${dm.dm_type}`)}</Badge>
        </CardTitle></CardHeader></summary>
        {activeDm === dm.dm_id ? <CardContent>
          <Tree dmId={dm.dm_id} nodes={dm.tree?.children ?? []} open={open} onToggle={onToggle}
            overrides={overrides} onOverride={onOverride} />
        </CardContent> : null}
      </details>
    </Card>)}
    <div className="sticky bottom-0 z-10 flex justify-between gap-3 border-t border-md bg-card p-4">
      <Button type="button" variant="secondary" disabled={wizard.busy}
        onClick={() => void wizard.action("back")}>{t("common.back")}</Button>
      <Button type="button" disabled={wizard.busy} onClick={advance}>{t("migration.structure.validate")}</Button>
    </div>
  </div>;
}
