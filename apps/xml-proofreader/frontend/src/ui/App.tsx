import { useEffect, useState } from "react";
import { useStore } from "./store";
import { useSession } from "./sessionStore";
import { Viewer } from "./viewer/Viewer";
import { RightPanel } from "./comments/CommentsPanel";
import { Login } from "./auth/Login";
import { SettingsModal } from "./auth/SettingsModal";
import { ThemeToggle } from "./ThemeToggle";
import { BRANDING } from "../branding";
import { initials } from "../core/auth/types";
import { languageMismatch } from "../core/workspace/types";

function IconFolder() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}

function IconChevronDown() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.6 1.6 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.6 1.6 0 0 0-1.82-.33 1.6 1.6 0 0 0-1 1.46V21a2 2 0 1 1-4 0v-.09a1.6 1.6 0 0 0-1-1.46 1.6 1.6 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.6 1.6 0 0 0 4.6 15a1.6 1.6 0 0 0-1.46-1H3a2 2 0 1 1 0-4h.09a1.6 1.6 0 0 0 1.46-1 1.6 1.6 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.6 1.6 0 0 0 1.82.33h.01a1.6 1.6 0 0 0 1-1.46V3a2 2 0 1 1 4 0v.09a1.6 1.6 0 0 0 1 1.46h.01a1.6 1.6 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.6 1.6 0 0 0-.33 1.82v.01a1.6 1.6 0 0 0 1.46 1H21a2 2 0 1 1 0 4h-.09a1.6 1.6 0 0 0-1.46 1z" />
    </svg>
  );
}

function IconLogOut() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  );
}

function IconOpen() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3v12" />
      <path d="M7 10l5 5 5-5" />
      <path d="M5 21h14" />
    </svg>
  );
}

function IconSave() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M17 21v-8H7v8" />
      <path d="M7 3v5h8" />
    </svg>
  );
}

function IconExport() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 21V9" />
      <path d="M17 14l-5-5-5 5" />
      <path d="M5 3h14" />
    </svg>
  );
}

function IconCheckCircle() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function IconEyeHalf() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z" />
      <path d="M2 12h20" />
    </svg>
  );
}

export function App() {
  const [reportOpen, setReportOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [leftTab, setLeftTab] = useState<"documents" | "review" | "settings" | "data">("documents");
  const save = useStore((s) => s.save);
  const ready = useSession((s) => s.ready);
  const user = useSession((s) => s.user);
  const init = useSession((s) => s.init);

  useEffect(() => { init(); }, [init]);

  useEffect(() => {
    document.title = `${BRANDING.name} — ${BRANDING.tagline}`;
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
      if (e.key === "Escape") { setReportOpen(false); setSettingsOpen(false); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  if (!ready) return null;
  if (!user) return <Login />;

  return (
    <div className="app-root">
      <TopBar onSettings={() => setSettingsOpen(true)} />
      <div className="app">
        <Sidebar
          tab={leftTab}
          onTabChange={setLeftTab}
          onReport={() => setReportOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        <Viewer />
        <RightPanel />
      </div>
      {reportOpen && <ReportModal onClose={() => setReportOpen(false)} />}
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
      <Toasts />
    </div>
  );
}

function TopBar({ onSettings }: { onSettings: () => void }) {
  const fileName = useStore((s) => s.fileName);
  const dirty = useStore((s) => s.dirty);
  const saveUri = useStore((s) => s.saveUri);
  const language = useStore((s) => s.language);
  const version = useStore((s) => s.version);
  const languageError = useStore((s) => s.languageError);
  const sessionUser = useSession((s) => s.user)!;
  const logout = useSession((s) => s.logout);
  const projects = useSession((s) => s.settings.projects);
  const currentProjectId = useSession((s) => s.settings.currentProjectId);
  const setProject = useSession((s) => s.setProject);
  const [menu, setMenu] = useState(false);

  const project = projects.find((p) => p.id === currentProjectId) ?? projects[0];
  // Workspace validation: does the loaded document match the project's expectations?
  const mismatch = languageMismatch(language, version, project);
  const status = dirty
    ? { cls: "unsaved", label: "● Unsaved changes" }
    : saveUri
      ? { cls: "saved", label: "● Saved" }
      : { cls: "", label: "● Working copy" };

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!(e.target as HTMLElement).closest(".userbox")) setMenu(false); };
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  return (
    <div className="topbar">
      <div className="proj-pick" title="Company project — fixes expected language, issue and repository">
        <span className="top-icon"><IconFolder /></span>
        <select value={project?.id} onChange={(e) => setProject(e.target.value)}>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      <div className="doc-meta">
        <span className="pill">{fileName || "No document"}</span>
        {language && (
          <span className={`pill${mismatch ? " ctx-warn" : ""}`}
            title={mismatch ? `Document is ${language} ${version} but project expects ${project.language} ${project.issue}` : "Auto-detected from the loaded XML"}>
            <b style={{ color: mismatch ? "var(--comment)" : "var(--color-accent-purple)" }}>{language}</b>{version ? ` ${version}` : ""}
          </span>
        )}
        {languageError && (
          <span className="pill ctx-warn" title={languageError.detail}>Unsupported: {languageError.name}</span>
        )}
        {fileName && !languageError && <span className="pill"><span className={status.cls}>{status.label}</span></span>}
      </div>
      <div className="spacer" />
      <div className="who userbox" style={{ position: "relative" }}>
        <div className="userbtn" onClick={(e) => { e.stopPropagation(); setMenu((v) => !v); }}>
          <div className="avatar">{initials(sessionUser.name)}</div>
          <span className="nm">{sessionUser.name}</span>
          <span className="top-icon"><IconChevronDown /></span>
        </div>
        {menu && (
          <div className="usermenu show">
            <div className="uhead"><div className="n">{sessionUser.name}</div><div className="e">{sessionUser.email}</div></div>
            <button onClick={() => { setMenu(false); onSettings(); }}><span className="menu-icon"><IconSettings /></span>Settings</button>
            <button onClick={() => { setMenu(false); logout(); }}><span className="menu-icon"><IconLogOut /></span>Sign out</button>
          </div>
        )}
      </div>
    </div>
  );
}

function Sidebar({
  tab,
  onTabChange,
  onReport,
  onOpenSettings,
}: {
  tab: "documents" | "review" | "settings" | "data";
  onTabChange: (tab: "documents" | "review" | "settings" | "data") => void;
  onReport: () => void;
  onOpenSettings: () => void;
}) {
  const openFile = useStore((s) => s.openFile);
  const save = useStore((s) => s.save);
  const saveAs = useStore((s) => s.saveAs);
  const outline = useStore((s) => s.rendered.outline);
  const comments = useStore((s) => s.comments);
  // F2 (ADR-0025): showResolved is authoritative in sessionStore.prefs.
  const showResolved = useSession((s) => s.settings.prefs.showResolved);
  const updateSettings = useSession((s) => s.updateSettings);
  const hasDoc = useStore((s) => s.buffer.length > 0);
  const mapModel = useStore((s) => s.mapModel);
  const merged = useStore((s) => s.merged);
  const openTopicByHref = useStore((s) => s.openTopicByHref);
  const rightMode = useStore((s) => s.rightMode);
  const setRight = useStore((s) => s.setRight);
  const issues = useStore((s) => s.issues);
  const chatMessages = useStore((s) => s.chatMessages);
  const runProviders = useStore((s) => s.runProviders);
  const setIssues = useStore((s) => s.setIssues);
  const clearChat = useStore((s) => s.clearChat);
  const setFilter = useStore((s) => s.setFilter);
  const setSearch = useStore((s) => s.setSearch);
  const isMap = mapModel !== null && !merged;
  const sessionUser = useSession((s) => s.user)!;
  const settings = useSession((s) => s.settings);
  const projects = useSession((s) => s.settings.projects);
  const currentProjectId = useSession((s) => s.settings.currentProjectId);
  const project = projects.find((p) => p.id === currentProjectId) ?? projects[0];
  const resolved = comments.filter((c) => c.resolved).length;
  const graderAvailable = useStore((s) => s.graderAvailable);
  const chatAvailable = useStore((s) => s.chatAvailable);

  function toggleShowResolved() {
    const prefs = useSession.getState().settings.prefs;
    void updateSettings({ prefs: { ...prefs, showResolved: !prefs.showResolved } });
  }

  function setUiLanguage(lang: "en" | "fr") {
    const prefs = useSession.getState().settings.prefs;
    void updateSettings({ prefs: { ...prefs, uiLanguage: lang } });
  }

  const llmStatus = (!graderAvailable && !chatAvailable)
    ? "OFF"
    : settings.ai.apiKey
      ? "ON"
      : "NO KEY";

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span
          className="brand"
          title="Structured content validation for DITA / S1000D"
          style={{ cursor: "help" }}
        >
          {BRANDING.name}
        </span>
        <span className="version">v{BRANDING.version}</span>
        <ThemeToggle />
      </div>

      <div className="llm-status" title="Statut LLM (clé + disponibilité runtime)">
        <span>LLM</span>
        <span className={`llm-badge${llmStatus === "ON" ? " on" : llmStatus === "OFF" ? " off" : " warn"}`}>{llmStatus}</span>
      </div>

      <nav className="sidebar-nav" aria-label="Navigation principale">
        <button className={tab === "documents" ? "nav-item active" : "nav-item"} onClick={() => onTabChange("documents")}>Documents</button>
        <button className={tab === "review" ? "nav-item active" : "nav-item"} onClick={() => onTabChange("review")}>Review</button>
        <button className={tab === "settings" ? "nav-item active" : "nav-item"} onClick={() => onTabChange("settings")}>Settings</button>
        <button className={tab === "data" ? "nav-item active" : "nav-item"} onClick={() => onTabChange("data")}>Données</button>
      </nav>

      {tab === "documents" && (
        <>
      <div className="side-section">
        <div className="side-label">Document</div>
        <button className="side-btn primary" onClick={openFile}><span className="ic"><IconOpen /></span> Open XML…</button>
        <button className="side-btn" onClick={save} disabled={!hasDoc}><span className="ic"><IconSave /></span> Save <span className="kbd">Ctrl S</span></button>
        <button className="side-btn" onClick={saveAs} disabled={!hasDoc}><span className="ic"><IconExport /></span> Export / Save as…</button>
      </div>
      <div className="side-divider" />
      <div className="side-section" style={{ paddingBottom: 4 }}><div className="side-label">Document outline</div></div>
      <nav className="outline">
        {outline.map((o) => (
          <div
            key={o.id}
            className={"outline-item lvl" + o.level + (isMap ? " mapnode" : "")}
            onClick={() => { if (o.href && isMap) openTopicByHref(o.href); else scrollTo(o.id); }}
          >{o.text}</div>
        ))}
      </nav>
        </>
      )}

      {tab === "review" && (
        <>
      <div className="side-section" style={{ paddingBottom: 2 }}>
        <div className="side-label">Review</div>
        <button className="side-btn" onClick={onReport}><span className="ic"><IconCheckCircle /></span> Review summary</button>
        <button className={`side-btn${showResolved ? " active" : ""}`} onClick={toggleShowResolved}>
          <span className="ic"><IconEyeHalf /></span> {showResolved ? "Hide resolved" : "Show resolved"}
        </button>
        <button className={rightMode === "comments" ? "side-btn active" : "side-btn"} onClick={() => setRight("comments")}>Comments panel</button>
        <button className={rightMode === "issues" ? "side-btn active" : "side-btn"} onClick={() => setRight("issues")}>Issues panel</button>
        <button className={rightMode === "proofreader" ? "side-btn active" : "side-btn"} onClick={() => setRight("proofreader")}>AI Proofreader</button>
      </div>
      <div className="side-divider" />
        </>
      )}

      {tab === "settings" && (
        <>
      <div className="side-section">
        <div className="side-label">Settings</div>
        <button className="side-btn primary" onClick={onOpenSettings}><span className="ic"><IconSettings /></span> Open Mistral config</button>
        <button className={rightMode === "chat" ? "side-btn active" : "side-btn"} onClick={() => setRight("chat")}>AI Chat panel</button>
      </div>
      <div className="side-divider" />
      <div className="side-section side-card">
        <div className="side-label">Mistral status</div>
        <div className="side-kv"><span>Provider</span><b>{settings.ai.provider}</b></div>
        <div className="side-kv"><span>Model</span><b>{settings.ai.model}</b></div>
        <div className="side-kv"><span>API key</span><b>{settings.ai.apiKey ? "Configured" : "Not configured"}</b></div>
      </div>
        </>
      )}

      {tab === "data" && (
        <>
      <div className="side-section">
        <div className="side-label">Données</div>
        <div className="side-kv"><span>Comments</span><b>{comments.length}</b></div>
        <div className="side-kv"><span>Issues</span><b>{issues.length}</b></div>
        <div className="side-kv"><span>Chat messages</span><b>{chatMessages.length}</b></div>
        <button className="side-btn" onClick={() => void runProviders()}>Re-run checks</button>
        <button className="side-btn" onClick={() => setIssues([])}>Clear issues</button>
        <button className="side-btn" onClick={clearChat}>Clear chat</button>
        <button className="side-btn" onClick={() => { setFilter("all"); setSearch(""); }}>Reset filters</button>
      </div>
        </>
      )}

      <div className="side-divider" />
      <div className="lang-switch" role="group" aria-label="Language">
        <button className={settings.prefs.uiLanguage === "fr" ? "lang-btn active" : "lang-btn"} onClick={() => setUiLanguage("fr")}>FR</button>
        <button className={settings.prefs.uiLanguage === "en" ? "lang-btn active" : "lang-btn"} onClick={() => setUiLanguage("en")}>EN</button>
      </div>
      <div className="side-foot">
        Reviewer: <b>{sessionUser.name}</b><br />
        Project: {project?.name ?? "—"}<br />
        {comments.length} comment{comments.length !== 1 ? "s" : ""} · {resolved} resolved
      </div>
    </aside>
  );
}

function ReportModal({ onClose }: { onClose: () => void }) {
  const comments = useStore((s) => s.comments);
  const open = comments.filter((c) => !c.resolved).length;
  const resolved = comments.length - open;
  const SWATCH: Record<string, string> = { yellow: "var(--hl-yellow)", green: "var(--hl-green)", pink: "var(--hl-pink)", blue: "var(--hl-blue)" };
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h3>Review summary <button className="x" onClick={onClose}>×</button></h3>
        <div className="mbody">
          <div className="stat-grid">
        <div className="stat"><div className="n" style={{ color: "var(--accent)" }}>{comments.length}</div><div className="l">Comments</div></div>
        <div className="stat"><div className="n" style={{ color: "var(--comment)" }}>{open}</div><div className="l">Open</div></div>
        <div className="stat"><div className="n" style={{ color: "var(--ok)" }}>{resolved}</div><div className="l">Resolved</div></div>
          </div>
          <div style={{ maxHeight: "40vh", overflow: "auto" }}>
            {comments.map((c) => (
              <div key={c.id} style={{ display: "flex", gap: 9, alignItems: "flex-start", padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
                <span className="swatch-sm" style={{ background: SWATCH[c.color], marginTop: 3 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>“{c.anchor.quote}”</div>
                  <div style={{ fontSize: 13, marginTop: 2 }}>{c.text || <i style={{ color: "var(--muted)" }}>no text</i>}</div>
                </div>
                <span className={`status-tag ${c.resolved ? "done" : "open"}`}>{c.resolved ? "Resolved" : "Open"}</span>
              </div>
            ))}
            {comments.length === 0 && <div style={{ color: "var(--muted)", padding: "14px 0" }}>No comments.</div>}
          </div>
        </div>
        <div className="mfoot"><button className="btn primary" onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}

function Toasts() {
  const toasts = useStore((s) => s.toasts);
  return (
    <div className="toast-wrap">
      {toasts.map((t) => (
        <div key={t.id} className="toast">{t.msg}</div>
      ))}
    </div>
  );
}
