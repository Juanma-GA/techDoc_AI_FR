// Miroir du contrat backend (app/flow/model.py + app/schemas.py).

export const NODE_TYPES = [
  "start",
  "end",
  "process",
  "decision",
  "io",
  "document",
  "subprocess",
  "connector",
  "check",
  "repair",
  "safety",
] as const;
export type NodeType = (typeof NODE_TYPES)[number];

export type Lane = { id: string; label: string };

export type FlowNode = {
  id: string;
  label: string;
  type: NodeType;
  lane?: string | null;
  ref?: string | null;
  expected?: string | null;
  tools?: string | null;
  warning?: string | null;
  duration?: string | null;
};

export type FlowEdge = { source: string; target: string; label?: string };

export type FlowGraph = {
  title: string;
  direction: "TB" | "LR";
  system?: string | null;
  fault_code?: string | null;
  lanes: Lane[];
  nodes: FlowNode[];
  edges: FlowEdge[];
};

export type SourceType = "text" | "table" | "json" | "dsl";

export type ParseResult = { graph: FlowGraph; warnings: string[]; llm_used: boolean };

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type AssistantDocument = { name: string; text: string };

export type AttachResult = {
  kind: "graph" | "document";
  name: string;
  graph: FlowGraph | null;
  text: string;
  truncated: boolean;
  warnings: string[];
};

export type AssistantReply = {
  message: string;
  graph: FlowGraph | null;
  changed: boolean;
  llm_used: boolean;
  warnings: string[];
};

export type FlowSummary = {
  id: string;
  name: string;
  source_type: SourceType;
  node_count: number;
  edge_count: number;
  created_at: string;
  updated_at: string;
};

export type FlowOut = FlowSummary & { source_text: string; graph: FlowGraph };

export type FlowCreate = {
  name: string;
  source_type: SourceType;
  source_text: string;
  graph: FlowGraph;
};

export type FormatInfo = { format: string; extension: string; media_type: string };

export type AdminStats = { flows: number; nodes: number; edges: number };
export type AdminReset = { scope: string; deleted: Record<string, number> };
