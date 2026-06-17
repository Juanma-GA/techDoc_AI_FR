import { Folder, FileText } from "lucide-react";

import type { TreeNodeDto } from "../../lib/api";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1048576).toFixed(2)} MB`;
}

function Node({ node }: { node: TreeNodeDto }) {
  const isFolder = node.kind === "folder";
  return (
    <li>
      <span className="flex items-center gap-1.5 py-0.5">
        {isFolder ? (
          <Folder size={13} className="shrink-0 text-brand-blue-light" aria-hidden="true" />
        ) : (
          <FileText size={13} className="shrink-0 text-fg-muted" aria-hidden="true" />
        )}
        <span className={isFolder ? "text-brand-blue-light" : "text-fg-dim"}>{node.name}</span>
        {!isFolder ? (
          <span className="text-label text-fg-muted">{formatBytes(node.size)}</span>
        ) : null}
      </span>
      {node.children.length ? (
        <ul className="ml-2 border-l border-md pl-3">
          {node.children.map((c) => (
            <Node key={c.id} node={c} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function TreeView({ nodes }: { nodes: TreeNodeDto[] }) {
  if (!nodes.length) return <p className="text-fg-dim">Arborescence vide.</p>;
  return (
    <ul className="max-h-[420px] overflow-y-auto font-mono text-sm">
      {nodes.map((n) => (
        <Node key={n.id} node={n} />
      ))}
    </ul>
  );
}
