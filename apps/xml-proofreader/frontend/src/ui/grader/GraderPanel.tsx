// AI Proofreader panel: numbered rule cards + Proofread button.
// Results are routed to the Issues tab (source "proofreader") via store.setIssues.
// Tauri-only: the Proofread button is disabled in the browser (no LlmPort available).
// Note: rules are persisted under settings.graderRules (key unchanged for backwards-compat).
import { useState } from "react";
import { useStore } from "../store";
import { useSession } from "../sessionStore";

export function GraderPanel() {
  const graderAvailable = useStore((s) => s.graderAvailable);
  const runGrader = useStore((s) => s.runGrader);
  const setRight = useStore((s) => s.setRight);

  const settings = useSession((s) => s.settings);
  const updateSettings = useSession((s) => s.updateSettings);

  const [rules, setRules] = useState<string[]>(settings.graderRules);
  const [newRule, setNewRule] = useState("");
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [running, setRunning] = useState(false);

  async function persistRules(next: string[]) {
    setRules(next);
    await updateSettings({ graderRules: next });
  }

  async function addRule() {
    const text = newRule.trim();
    if (!text) return;
    await persistRules([...rules, text]);
    setNewRule("");
  }

  async function deleteRule(idx: number) {
    await persistRules(rules.filter((_, i) => i !== idx));
    if (editingIdx === idx) setEditingIdx(null);
  }

  function startEdit(idx: number) {
    setEditingIdx(idx);
    setEditingText(rules[idx]);
  }

  async function commitEdit(idx: number) {
    const text = editingText.trim();
    if (!text) { setEditingIdx(null); return; }
    const next = rules.map((r, i) => (i === idx ? text : r));
    await persistRules(next);
    setEditingIdx(null);
  }

  async function handleProofread() {
    if (!graderAvailable || running) return;
    setRunning(true);
    try {
      await runGrader();
      setRight("issues");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rp-body">
      <div className="pr-header">
        <div className="pr-title">AI Proofreader</div>
        <div className="pr-subtitle">SME proofreading rules</div>
      </div>

      <div className="pr-rules">
        {rules.length === 0 && (
          <div className="pr-empty">No rules yet. Add your first rule below.</div>
        )}
        {rules.map((rule, idx) => (
          <div key={idx} className="pr-card">
            <span className="pr-num">{idx + 1}</span>
            {editingIdx === idx ? (
              <input
                className="pr-edit-input"
                value={editingText}
                autoFocus
                onChange={(e) => setEditingText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitEdit(idx);
                  if (e.key === "Escape") setEditingIdx(null);
                }}
                onBlur={() => commitEdit(idx)}
              />
            ) : (
              <span className="pr-rule-text">{rule}</span>
            )}
            <div className="pr-card-actions">
              <button
                className="pr-btn-icon"
                title="Edit rule"
                onClick={() => (editingIdx === idx ? commitEdit(idx) : startEdit(idx))}
              >
                Edit
              </button>
              <button
                className="pr-btn-icon pr-btn-delete"
                title="Delete rule"
                onClick={() => deleteRule(idx)}
              >
                ×
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="pr-add">
        <input
          className="pr-new-input"
          value={newRule}
          onChange={(e) => setNewRule(e.target.value)}
          placeholder="Write a new proofreading rule…"
          onKeyDown={(e) => { if (e.key === "Enter") addRule(); }}
        />
      </div>

      <div className="pr-run">
        {!graderAvailable && (
          <div className="pr-unavail">AI Proofreader requires the desktop app (Tauri). Not available in the browser.</div>
        )}
        <button
          className="btn pr-btn-run"
          disabled={!graderAvailable || running}
          onClick={handleProofread}
        >
          {running ? "Proofreading…" : "🪄 Proofread document"}
        </button>
        <div className="pr-hint">Results appear in the Issues tab.</div>
      </div>
    </div>
  );
}
