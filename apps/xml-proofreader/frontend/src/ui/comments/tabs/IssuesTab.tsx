import { useStore } from "../../store";
import { useSession } from "../../sessionStore";
import { locateQuote } from "../../../core/issues/anchor";

function IconOkCircle() {
  return (
    <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.5 11 15l4.5-4.5" />
    </svg>
  );
}

export function IssuesTabBadge() {
  const n = useStore((s) => s.issues.length);
  return <>{n}</>;
}

export function IssuesTab() {
  const issues = useStore((s) => s.issues);
  const languageError = useStore((s) => s.languageError);
  const activeIssueId = useStore((s) => s.activeIssueId);
  const store = useStore();
  const buffer = useStore((s) => s.buffer);
  const defaultHighlight = useSession((s) => s.settings.prefs.defaultHighlight);
  const SEVCOL: Record<string, string> = { error: "var(--danger)", warning: "var(--comment)", info: "var(--accent)" };

  function rerun() {
    void store.runProviders();
  }

  if (!issues.length && !languageError) {
    return (
      <div className="rp-body">
        <div className="empty"><div className="big" aria-hidden="true"><IconOkCircle /></div>No issues. Validation and tool checks (Oxygen, AI Proofreader) will appear here.</div>
        {buffer && <div style={{ padding: "0 14px 14px" }}><button className="side-btn" onClick={rerun} style={{ width: "100%" }}>Re-run checks</button></div>}
      </div>
    );
  }
  return (
    <div className="rp-body">
      {buffer && (
        <div className="rp-toolbar">
          <button onClick={rerun} style={{ fontSize: 11 }}>Re-run checks</button>
          <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: "auto" }}>{issues.length} issue{issues.length !== 1 ? "s" : ""}</span>
        </div>
      )}
      <div className="comments-list">
        {languageError && (
          <div className="icard" style={{ borderLeft: "4px solid var(--danger)" }}>
            <div className="ih"><span className="src" style={{ background: "var(--muted)" }}>LANGUAGE</span>
              <span className="sev" style={{ color: "var(--danger)", marginLeft: "auto" }}>error</span></div>
            <div className="msg">Unsupported document language: <b>{languageError.name}</b>.</div>
          </div>
        )}
        {issues.map((is) => {
          // G2 (ADR-0032): Accept is enabled whenever there is a suggestion;
          // locateQuote is used only to show exact vs approximate anchor in title.
          const exactAnchor = !!(is.suggestion && is.quote && locateQuote(buffer, is.quote));
          return (
          <div
            key={is.id}
            className={`icard${activeIssueId === is.id ? " active" : ""}`}
            style={{ borderLeft: `4px solid ${SEVCOL[is.severity]}` }}
            onClick={() => store.goToIssue(is.id)}
          >
            <div className="ih">
              <span className="src">{is.source}</span>
              <span className="sev" style={{ color: SEVCOL[is.severity], marginLeft: "auto" }}>{is.severity}</span>
            </div>
            <div className="msg">{is.message}</div>
            {is.quote && <div className="q">"{is.quote}"</div>}
            {is.suggestion && <div className="sugg">Suggestion: <b>{is.suggestion}</b></div>}
            <div className="actions" onClick={(e) => e.stopPropagation()}>
              {is.anchor && (
                <button onClick={() => store.goToIssue(is.id)}>Go</button>
              )}
              {is.suggestion && (
                <button
                  style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
                  title={exactAnchor
                    ? "Add the suggestion as a comment (exact anchor; document text is not changed)"
                    : "Add the suggestion as a comment (approximate or stored anchor)"}
                  onClick={() => store.acceptSuggestion(is.id, defaultHighlight)}
                >Accept as comment</button>
              )}
              <button onClick={() => store.ignoreIssue(is.id)}>Ignore</button>
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}
