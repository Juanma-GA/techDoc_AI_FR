// AI Chat panel (B8c + C5). Tauri-only: chat is disabled in the browser.
// Tool calls proposed by the AI appear as pending cards; they only execute
// after explicit user approval (Approve button). Rejecting is always safe.
//
// C5 additions: curated action chips + "All MCP tools" expandable list.
import { useRef, useEffect, useState } from "react";
import { useStore } from "../store";
import type { ChatMessage, ToolCallProposal } from "./types";
import type { Finding } from "../../core/findings/types";
import { CURATED_ACTIONS, type CuratedAction } from "./actions";
import type { McpTool } from "../../ports/McpPort";

export function ChatPanel() {
  const chatAvailable = useStore((s) => s.chatAvailable);
  const chatMessages = useStore((s) => s.chatMessages);
  const chatPending = useStore((s) => s.chatPending);
  const sendChat = useStore((s) => s.sendChat);
  const detectChatIssues = useStore((s) => s.detectChatIssues);
  const addFindingsToIssues = useStore((s) => s.addFindingsToIssues);
  const approveToolCall = useStore((s) => s.approveToolCall);
  const rejectToolCall = useStore((s) => s.rejectToolCall);
  const clearChat = useStore((s) => s.clearChat);
  const listMcpTools = useStore((s) => s.listMcpTools);
  const directInvokeTool = useStore((s) => s.directInvokeTool);
  const buffer = useStore((s) => s.buffer);

  function IconAiMessage() {
    return (
      <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
        <path d="M9 10h6M9 14h4" />
      </svg>
    );
  }

  // E4: while streaming, the assistant bubble fills in place — so suppress the
  // standalone "Thinking…" placeholder once the last assistant message has text.
  const lastMsg = chatMessages[chatMessages.length - 1];
  const streaming = chatPending && lastMsg?.role === "assistant" && lastMsg.text.length > 0;

  const [input, setInput] = useState("");
  const [toolsOpen, setToolsOpen] = useState(false);
  const [toolsList, setToolsList] = useState<McpTool[]>([]);
  const [toolsLoading, setToolsLoading] = useState(false);
  const [toolsError, setToolsError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages.length, chatPending]);

  function handleSend() {
    const text = input.trim();
    if (!text || chatPending || !chatAvailable) return;
    setInput("");
    void sendChat(text);
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleCuratedAction(action: CuratedAction) {
    if (chatPending || !chatAvailable) return;
    if (action.detect) void detectChatIssues(action.prompt);
    else void sendChat(action.prompt);
  }

  async function handleToggleTools() {
    if (toolsOpen) {
      setToolsOpen(false);
      return;
    }
    setToolsLoading(true);
    setToolsError(null);
    setToolsList([]);
    try {
      const tools = await listMcpTools();
      setToolsList(tools);
      setToolsOpen(true);
    } catch (e) {
      setToolsError(String(e instanceof Error ? e.message : e));
      setToolsOpen(true);
    } finally {
      setToolsLoading(false);
    }
  }

  function handleInvokeTool(tool: McpTool) {
    if (chatPending || !chatAvailable) return;
    setToolsOpen(false);
    directInvokeTool(tool.name);
  }

  if (!chatAvailable) {
    return (
      <div className="rp-body">
        <div className="empty">
          <div className="big" aria-hidden="true"><IconAiMessage /></div>
          AI Chat requires the desktop app (Tauri). Not available in the browser.
        </div>
      </div>
    );
  }

  return (
    <div className="rp-body chat-panel">
      <div className="chat-toolbar">
        <span style={{ fontSize: 11, color: "var(--muted)" }}>
          {chatMessages.length > 0 ? `${chatMessages.length} message(s)` : "Start a conversation"}
        </span>
        {chatMessages.length > 0 && (
          <button style={{ fontSize: 11 }} onClick={clearChat}>Clear</button>
        )}
      </div>

      {/* ── Curated action chips ─────────────────────────────────────────── */}
      <div className="chat-quick-actions">
        {CURATED_ACTIONS.map((a) => (
          <button
            key={a.label}
            className="chat-action-chip"
            disabled={chatPending}
            onClick={() => handleCuratedAction(a)}
            title={a.prompt}
          >
            {a.label}
          </button>
        ))}
        <button
          className={`chat-action-chip chat-action-chip--tools${toolsOpen ? " active" : ""}`}
          disabled={chatPending || toolsLoading}
          onClick={() => void handleToggleTools()}
          title="Show all available MCP tools"
        >
          {toolsLoading ? "Loading…" : "All tools"}
        </button>
      </div>

      {/* ── All-tools panel ──────────────────────────────────────────────── */}
      {toolsOpen && (
        <div className="chat-tools-list">
          {toolsError ? (
            <div className="chat-tools-error">{toolsError}</div>
          ) : toolsList.length === 0 ? (
            <div className="chat-tools-empty">No tools available.</div>
          ) : (
            toolsList.map((tool) => (
              <div key={tool.name} className="chat-tool-entry">
                <div className="chat-tool-info">
                  <span className="chat-tool-name">{tool.name}</span>
                  {tool.description && (
                    <span className="chat-tool-desc">{tool.description}</span>
                  )}
                </div>
                <button
                  className="btn"
                  style={{ fontSize: 11, padding: "2px 8px" }}
                  disabled={chatPending}
                  onClick={() => handleInvokeTool(tool)}
                >
                  Run
                </button>
              </div>
            ))
          )}
        </div>
      )}

      <div className="chat-messages">
        {!buffer && (
          <div className="chat-hint">Open a document to give the assistant context.</div>
        )}
        {chatMessages.map((m) => (
          <MessageCard
            key={m.id}
            message={m}
            onApprove={(callId) => void approveToolCall(m.id, callId)}
            onReject={(callId) => rejectToolCall(m.id, callId)}
            onSendFindings={addFindingsToIssues}
          />
        ))}
        {chatPending && !streaming && (
          <div className="chat-msg assistant">
            <span className="chat-role">Assistant</span>
            <span className="chat-thinking">Thinking…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          rows={3}
          placeholder="Ask a question about the document… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={chatPending}
        />
        <button
          className="btn primary"
          disabled={!input.trim() || chatPending}
          onClick={handleSend}
        >
          Send
        </button>
      </div>
    </div>
  );
}

function MessageCard({
  message,
  onApprove,
  onReject,
  onSendFindings,
}: {
  message: ChatMessage;
  onApprove: (callId: string) => void;
  onReject: (callId: string) => void;
  onSendFindings: (findings: Finding[]) => void;
}) {
  const findings = message.findings ?? [];
  return (
    <div className={`chat-msg ${message.role}`}>
      <span className="chat-role">{message.role === "user" ? "You" : "Assistant"}</span>
      {message.text && <p className="chat-text">{message.text}</p>}
      {message.toolCalls.map((tc) => (
        <ToolCallCard key={tc.id} tc={tc} onApprove={onApprove} onReject={onReject} />
      ))}
      {findings.length > 0 && (
        <div className="chat-findings">
          {findings.map((f, i) => (
            <FindingCard key={i} f={f} onSend={() => onSendFindings([f])} />
          ))}
          {findings.length > 1 && (
            <button className="cf-send-all" onClick={() => onSendFindings(findings)}>
              Send all to Issues ({findings.length})
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function FindingCard({ f, onSend }: { f: Finding; onSend: () => void }) {
  const sevColor: Record<string, string> = {
    error: "var(--danger)", warning: "var(--comment)", info: "var(--accent)",
  };
  return (
    <div className="chat-finding" style={{ borderLeft: `3px solid ${sevColor[f.severity]}` }}>
      <div className="cf-head"><span className="cf-sev" style={{ color: sevColor[f.severity] }}>{f.severity}</span></div>
      <div className="cf-msg">{f.message}</div>
      {f.quote && <div className="cf-quote">"{f.quote}"</div>}
      {f.replacement && <div className="cf-repl">Replacement: <b>{f.replacement}</b></div>}
      <button className="cf-send" onClick={onSend}>Send to Issues</button>
    </div>
  );
}

function ToolCallCard({
  tc,
  onApprove,
  onReject,
}: {
  tc: ToolCallProposal;
  onApprove: (callId: string) => void;
  onReject: (callId: string) => void;
}) {
  const statusColor =
    tc.status === "approved" ? "var(--accent)"
    : tc.status === "rejected" ? "var(--muted)"
: "var(--comment)";

  return (
    <div className="tool-call-card" style={{ borderLeft: `3px solid ${statusColor}` }}>
      <div className="tc-header">
        <span className="tc-name">Tool: {tc.toolName}</span>
        <span className="tc-status" style={{ color: statusColor }}>{tc.status}</span>
      </div>
      {Object.keys(tc.args).length > 0 && (
        <pre className="tc-args">{JSON.stringify(tc.args, null, 2)}</pre>
      )}
      {tc.status === "pending" && (
        <div className="tc-actions">
          <button
            style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
            onClick={() => onApprove(tc.id)}
          >
            Approve
          </button>
          <button onClick={() => onReject(tc.id)}>Reject</button>
        </div>
      )}
      {tc.result && (
        <pre className="tc-result">{tc.result}</pre>
      )}
      {tc.error && (
        <div className="tc-error" style={{ color: "var(--danger)" }}>Error: {tc.error}</div>
      )}
    </div>
  );
}
