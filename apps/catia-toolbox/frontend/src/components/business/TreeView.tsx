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
      <span className={isFolder ? "tree-node folder" : "tree-node file"}>
        {isFolder ? (
          <Folder size={13} className="shrink-0" aria-hidden="true" />
        ) : (
          <FileText size={13} className="shrink-0" aria-hidden="true" />
        )}
        <span>{node.name}</span>
        {!isFolder ? <span className="tree-size">{formatBytes(node.size)}</span> : null}
      </span>
      {node.children.length ? (
        <ul>
          {node.children.map((c) => (
            <Node key={c.id} node={c} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function TreeView({ nodes }: { nodes: TreeNodeDto[] }) {
  if (!nodes.length) return <p className="hint">Arborescence vide.</p>;
  return (
    <div className="tree">
      <ul>
        {nodes.map((n) => (
          <Node key={n.id} node={n} />
        ))}
      </ul>
    </div>
  );
}
