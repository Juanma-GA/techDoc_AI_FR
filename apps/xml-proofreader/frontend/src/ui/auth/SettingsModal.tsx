// Per-user settings: AI/MCP, preferences, account. Persisted via the session
// store (associated to the signed-in user).
import { useState } from "react";
import { useSession } from "../sessionStore";

// Default value of settings.ai.oxygenMcpEndpoint (see src/core/workspace/types.ts).
// While the field still holds this placeholder the Oxygen MCP provider stays disabled.
const MCP_PLACEHOLDER = "stdio://oxygen-xml-28";

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const user = useSession((s) => s.user)!;
  const settings = useSession((s) => s.settings);
  const updateSettings = useSession((s) => s.updateSettings);
  const updateProfile = useSession((s) => s.updateProfile);
  const [tab, setTab] = useState<"ai" | "prefs" | "account">("ai");
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email);

  const setAi = (patch: Partial<typeof settings.ai>) =>
    updateSettings({ ai: { ...settings.ai, ...patch } });
  const setPrefs = (patch: Partial<typeof settings.prefs>) =>
    updateSettings({ prefs: { ...settings.prefs, ...patch } });

  return (
    <div className="modal-bg show" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h3>Settings <span style={{ fontWeight: 500, color: "var(--muted)" }}>- {user.name}</span>
          <button className="x" onClick={onClose}>×</button></h3>
        <div className="mbody">
          <div className="set-tabs">
            <button className={tab === "ai" ? "on" : ""} onClick={() => setTab("ai")}>AI &amp; MCP</button>
            <button className={tab === "prefs" ? "on" : ""} onClick={() => setTab("prefs")}>Preferences</button>
            <button className={tab === "account" ? "on" : ""} onClick={() => setTab("account")}>Account</button>
          </div>

          {tab === "ai" && (
            <>
              <Row k="AI provider" d="Used by AI Chat & Proofreader">
                <select value={settings.ai.provider} onChange={(e) => setAi({ provider: e.target.value as "anthropic" | "openai-compat" })}>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="openai-compat">OpenAI-compatible (Mistral, OpenAI, …)</option>
                </select>
              </Row>
              {settings.ai.provider === "openai-compat" && (
                <Row k="Base URL" d="e.g. https://api.mistral.ai/v1">
                  <input value={settings.ai.base_url ?? ""} placeholder="https://api.mistral.ai/v1"
                    onChange={(e) => setAi({ base_url: e.target.value })} />
                </Row>
              )}
              <Row k="Model" d="Default model">
                <input value={settings.ai.model} onChange={(e) => setAi({ model: e.target.value })} />
              </Row>
              <Row k="API key" d="Stored with your profile">
                <input type="password" value={settings.ai.apiKey} placeholder="sk-…"
                  onChange={(e) => setAi({ apiKey: e.target.value })} />
              </Row>
              <Row
                k="Oxygen MCP endpoint"
                d="Path to oxygen.bat / oxygenAuthor.bat (stdio), or an http:// URL. Requires Oxygen 28+ Enterprise with the MCP server enabled — see docs/oxygen-mcp-setup.md."
              >
                <input
                  value={settings.ai.oxygenMcpEndpoint}
                  placeholder="C:\Program Files\Oxygen XML Author 28\oxygenAuthor.bat"
                  onChange={(e) => setAi({ oxygenMcpEndpoint: e.target.value })}
                />
              </Row>
              {settings.ai.oxygenMcpEndpoint === MCP_PLACEHOLDER && (
                <div className="set-row" style={{ paddingTop: 0 }}>
                  <div />
                  <span style={{ fontSize: 12, color: "var(--comment)" }}>
                    Not configured - "{MCP_PLACEHOLDER}" is a placeholder. Replace it with a real
                    oxygen.bat path or an http:// URL to enable Oxygen MCP tools.
                  </span>
                </div>
              )}
              <Row k="Acrolinx / HyperSTE" d="Backlog — not configured">
                <span style={{ fontSize: 12, color: "var(--muted)" }}>— pending —</span>
              </Row>
            </>
          )}

          {tab === "prefs" && (
            <>
              <Row k="UI language">
                {/* TODO i18n — language persists but UI strings are not translated yet (F2, deferred) */}
                <select value={settings.prefs.uiLanguage} onChange={(e) => setPrefs({ uiLanguage: e.target.value as "en" | "fr" })}>
                  <option value="fr">Français</option><option value="en">English</option>
                </select>
              </Row>
              <Row k="Default highlight color">
                <select value={settings.prefs.defaultHighlight} onChange={(e) => setPrefs({ defaultHighlight: e.target.value as "yellow" })}>
                  <option value="yellow">Yellow</option><option value="green">Green</option>
                  <option value="pink">Pink</option><option value="blue">Blue</option>
                </select>
              </Row>
              <Row k="Show resolved comments">
                <input type="checkbox" checked={settings.prefs.showResolved} style={{ minWidth: "auto" }}
                  onChange={(e) => setPrefs({ showResolved: e.target.checked })} />
              </Row>
            </>
          )}

          {tab === "account" && (
            <>
              <Row k="Full name"><input value={name} onChange={(e) => setName(e.target.value)} /></Row>
              <Row k="Email"><input value={email} onChange={(e) => setEmail(e.target.value)} /></Row>
              <Row k="Company SSO" d="Future"><span style={{ fontSize: 12, color: "var(--muted)" }}>Not linked</span></Row>
            </>
          )}
        </div>
        <div className="mfoot">
          <button className="btn" onClick={onClose}>Close</button>
          {tab === "account" && (
            <button className="btn primary" onClick={() => { updateProfile(name, email); onClose(); }}>Save profile</button>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ k, d, children }: { k: string; d?: string; children: React.ReactNode }) {
  return (
    <div className="set-row">
      <div><div className="k">{k}</div>{d && <div className="d">{d}</div>}</div>
      {children}
    </div>
  );
}
