// Types for the AI Chat panel (Chunk 8 / B8c).
// A ChatMessage is either a user turn or an assistant turn.
// Assistant turns can carry tool-call proposals that require explicit approval.
import type { Finding } from "../../core/findings/types";

export type ToolCallStatus = "pending" | "approved" | "rejected";

export interface ToolCallProposal {
  id: string;
  toolName: string;
  args: Record<string, unknown>;
  status: ToolCallStatus;
  /** Result text from the MCP server, set after the call is approved and runs. */
  result?: string;
  /** Error text if the approved call failed. */
  error?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  /** Display text (tool_call tags stripped from assistant responses). */
  text: string;
  toolCalls: ToolCallProposal[];
  /** Structured findings from a "detect issues" action (D2); rendered as cards. */
  findings?: Finding[];
  timestamp: number;
}
