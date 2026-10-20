import type {
  AdminReset,
  AdminStats,
  AssistantDocument,
  AssistantReply,
  AttachResult,
  ChatMessage,
  FlowCreate,
  FlowGraph,
  FlowOut,
  FlowSummary,
  FormatInfo,
  ParseResult,
} from "../types/flow";
import { api, rawFetch } from "./api";

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const convertApi = {
  formats: () => api<FormatInfo[]>("/formats"),
  parseText: (text: string) => api<ParseResult>("/parse/text", json({ text })),
  parseJson: (content: string) => api<ParseResult>("/parse/json", json({ content })),
  parseTable: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return rawFetch("/parse/table", { method: "POST", body: form }).then(
      (r) => r.json() as Promise<ParseResult>,
    );
  },
  preview: (graph: FlowGraph) =>
    rawFetch("/render/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(graph),
    }).then((r) => r.blob()),
  render: (graph: FlowGraph, fmt: string) =>
    rawFetch(`/render/${encodeURIComponent(fmt)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(graph),
    }),
};

export const assistantApi = {
  chat: (messages: ChatMessage[], graph: FlowGraph | null, documents: AssistantDocument[]) =>
    api<AssistantReply>("/assistant/chat", json({ messages, graph, documents })),
  attach: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return rawFetch("/assistant/attach", { method: "POST", body: form }).then(
      (r) => r.json() as Promise<AttachResult>,
    );
  },
};

export const flowsApi = {
  list: () => api<FlowSummary[]>("/flows"),
  read: (id: string) => api<FlowOut>(`/flows/${id}`),
  create: (body: FlowCreate) => api<FlowOut>("/flows", json(body)),
  update: (id: string, body: Partial<FlowCreate>) =>
    api<FlowOut>(`/flows/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/flows/${id}`, { method: "DELETE" }),
  exportFile: (id: string, fmt: string) => rawFetch(`/flows/${id}/export/${encodeURIComponent(fmt)}`),
};

export const adminApi = {
  stats: () => api<AdminStats>("/admin/stats"),
  reset: (scope: "all" | "flows") => api<AdminReset>(`/admin/reset/${scope}`, { method: "POST" }),
};

/** Telecharge une reponse fichier en respectant le nom fourni par Content-Disposition. */
export async function saveResponse(response: Response, fallbackName: string): Promise<void> {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = match?.[1] ?? fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
