import { memo } from "react";
import { Badge, Button } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { PageFlag, RefFlag, ReviewFlag, TableFlag, ZoneFlag } from "../../../components/zoneFlags";
import type { TreeNode } from "../../../lib/api";

export type OverrideHandler = (dmId: string, nodeId: string, element: string) => void;
export const WizNode = memo(function WizNode({ dmId, node, override, onOverride }: {
  dmId: string; node: TreeNode; override?: string; onOverride: OverrideHandler;
}) {
  const { t } = useTranslation();
  return <span data-wiz-node={node.id} className="flex flex-wrap items-center gap-2 py-1 text-sm">
    <code className="text-info">{override ?? node.candidates[0]?.element ?? node.kind}</code>
    {node.confidence !== null && node.confidence < 0.6
      ? <Badge variant="warning">{t("migration.ui.lowConfidence")}</Badge> : null}
    {node.context !== "unknown" ? <Badge variant="info">{t(`dmType.${node.context}`)}</Badge> : null}
    {node.kind === "section" && node.level != null
      ? <Badge>{t("migration.structure.level", { level: node.level })}</Badge> : null}
    <PageFlag page={node.page} /><ZoneFlag zone={node.zone} /><ReviewFlag zone={node.zone} />
    <TableFlag kind={node.kind} /><RefFlag refs={node.refs} />
    {node.text ? <span className="min-w-0 grow truncate" title={node.text}>{node.text}</span> : null}
    {node.candidates.length > 1 ? node.candidates.map((candidate) =>
      <Button key={candidate.element} type="button" size="sm"
        variant={override === candidate.element ? "primary" : "ghost"}
        aria-pressed={override === candidate.element}
        onClick={() => onOverride(dmId, node.id, candidate.element)}>
        {t(override === candidate.element ? "migration.ui.selectedElement" : "migration.ui.useElement",
          { element: candidate.element })}
      </Button>) : null}
  </span>;
});
