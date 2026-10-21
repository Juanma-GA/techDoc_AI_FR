import { useTranslation } from "react-i18next";

import type { FlowGraph, FlowNode } from "../../types/flow";

const DETAILS: (keyof FlowNode)[] = ["ref", "expected", "tools", "warning", "duration"];

export function NodeTable({ graph }: { graph: FlowGraph }) {
  const { t } = useTranslation();
  const lanes = new Map(graph.lanes.map((l) => [l.id, l.label]));
  const outgoing = (id: string) =>
    graph.edges
      .filter((e) => e.source === id)
      .map((e) => (e.label ? `${e.target} (${e.label})` : e.target))
      .join(", ");

  return (
    <div className="overflow-auto rounded border">
      <table className="w-full text-left text-xs">
        <thead className="bg-bg-2 text-fg-dim">
          <tr>
            <th className="px-2 py-1">{t("editor.nodes.id")}</th>
            <th className="px-2 py-1">{t("editor.nodes.type")}</th>
            <th className="px-2 py-1">{t("editor.nodes.label")}</th>
            <th className="px-2 py-1">{t("editor.nodes.lane")}</th>
            <th className="px-2 py-1">{t("editor.nodes.next")}</th>
            {DETAILS.map((key) => (
              <th key={key} className="px-2 py-1">
                {t(`editor.nodes.${key}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {graph.nodes.map((node) => (
            <tr key={node.id} className="border-t align-top">
              <td className="px-2 py-1 font-mono">{node.id}</td>
              <td className="px-2 py-1">{t(`nodeTypes.${node.type}`)}</td>
              <td className="px-2 py-1">{node.label}</td>
              <td className="px-2 py-1">{node.lane ? (lanes.get(node.lane) ?? node.lane) : ""}</td>
              <td className="px-2 py-1 font-mono">{outgoing(node.id)}</td>
              {DETAILS.map((key) => (
                <td key={key} className={key === "warning" ? "px-2 py-1 text-warning" : "px-2 py-1"}>
                  {node[key] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
