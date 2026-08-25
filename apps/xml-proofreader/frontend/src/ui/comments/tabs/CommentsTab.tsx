import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { useStore } from "../../store";
import { useSession } from "../../sessionStore";
import type { ParsedComment } from "../../../core/oxygen/parse";
import type { Comment, HighlightColor } from "../../../core/model/types";

function IconCommentBubble() {
  return (
    <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H7l-4 3v-5.5A8.5 8.5 0 1 1 21 11.5z" />
    </svg>
  );
}

/**
 * Keeps an absolutely-positioned dropdown inside the scrollable right panel
 * (E1). The color menu is anchored to its button and would otherwise extend
 * past `.rp-body` (which clips it via `overflow:auto`) when the card sits near
 * the panel's right/bottom edge. On open we measure the menu against the panel
 * and flip it left/up when it would overflow. Measured in useLayoutEffect (runs
 * before paint), so there is no visible jump.
 */
function useMenuPlacement(open: boolean) {
  const anchorRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = useState<{ flipX: boolean; flipY: boolean }>({ flipX: false, flipY: false });

  useLayoutEffect(() => {
    if (!open) {
      setPlacement({ flipX: false, flipY: false });
      return;
    }
    const anchor = anchorRef.current;
    const menu = menuRef.current;
    if (!anchor || !menu) return;
    const bounds = (anchor.closest(".rp-body") ?? document.documentElement).getBoundingClientRect();
    const a = anchor.getBoundingClientRect();
    const m = menu.getBoundingClientRect();
    const PAD = 6; // keep a small gap from the panel edge
    setPlacement({
      flipX: a.left + m.width > bounds.right - PAD,
      flipY: a.bottom + 4 + m.height > bounds.bottom - PAD,
    });
  }, [open]);

  return { anchorRef, menuRef, placement };
}

const COLORS: HighlightColor[] = ["yellow", "green", "pink", "blue"];
const SWATCH_VAR: Record<HighlightColor, string> = {
  yellow: "var(--hl-yellow)", green: "var(--hl-green)", pink: "var(--hl-pink)", blue: "var(--hl-blue)",
};

function fmtTime(t: number): string {
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return "now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h`;
  return new Date(t).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

function fmtFull(t: number): string {
  return new Date(t).toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function CommentsTabBadge() {
  const n = useStore((s) => s.comments.length);
  return <>{n}</>;
}

export function CommentsTab() {
  const comments = useStore((s) => s.comments);
  const filter = useStore((s) => s.filter);
  const search = useStore((s) => s.search);
  // F2 (ADR-0025): showResolved is authoritative in sessionStore.prefs.
  const showResolved = useSession((s) => s.settings.prefs.showResolved);
  const setFilter = useStore((s) => s.setFilter);
  const setSearch = useStore((s) => s.setSearch);

  const shown = useMemo(() => {
    const q = search.toLowerCase();
    return comments.filter((c) => {
      if (filter === "open" && c.resolved) return false;
      if (filter === "resolved" && !c.resolved) return false;
      if (!showResolved && c.resolved) return false;
      if (q) {
        const inReplies = (c.replies ?? []).some((r) => r.text.toLowerCase().includes(q));
        if (!(c.text.toLowerCase().includes(q) || c.anchor.quote.toLowerCase().includes(q) || inReplies)) return false;
      }
      return true;
    });
  }, [comments, filter, search, showResolved]);

  return (
    <div className="rp-body">
      <div className="rp-toolbar">
        <select value={filter} onChange={(e) => setFilter(e.target.value as "all" | "open" | "resolved")}>
          <option value="all">All</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
        <input placeholder="Search comments…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <div className="comments-list">
        {shown.length === 0 ? (
          <div className="empty">
            <div className="big" aria-hidden="true"><IconCommentBubble /></div>
            {comments.length ? "No comments match the filter." : "No comments yet. Select text in the document to start."}
          </div>
        ) : (
          shown.map((c) => <CommentCard key={c.id} c={c} />)
        )}
      </div>
    </div>
  );
}

function ReplyBox({ targetId, onDone }: { targetId: string; onDone: () => void }) {
  const store = useStore();
  const [text, setText] = useState("");
  function send() {
    const t = text.trim();
    if (!t) return;
    store.reply(targetId, t);
    setText("");
    onDone();
  }
  return (
    <div className="reply-box" onClick={(e) => e.stopPropagation()}>
      <textarea autoFocus value={text} placeholder="Write a reply…" onChange={(e) => setText(e.target.value)} />
      <div className="actions">
        <button style={{ borderColor: "var(--accent)", color: "var(--accent)" }} onClick={send}>Send</button>
        <button onClick={onDone}>Cancel</button>
      </div>
    </div>
  );
}

function CommentCard({ c }: { c: ParsedComment }) {
  const activeId = useStore((s) => s.activeId);
  const store = useStore();
  const [replyOpen, setReplyOpen] = useState(false);

  return (
    <div
      className={`ccard ${c.resolved ? "resolved" : ""} ${activeId === c.id ? "active" : ""}`}
      onClick={() => store.setActive(c.id)}
    >
      <CommentNode c={c} isRoot />

      {(c.replies ?? []).length > 0 && (
        <div className="replies">
          {(c.replies ?? []).map((r) => <NestedNode key={r.id} c={r} />)}
        </div>
      )}

      {replyOpen ? (
        <ReplyBox targetId={c.id} onDone={() => setReplyOpen(false)} />
      ) : (
        <button className="reply-link" onClick={(e) => { e.stopPropagation(); setReplyOpen(true); }}>Reply</button>
      )}
    </div>
  );
}

/** Recursive component for rendering a reply and its nested replies. */
function NestedNode({ c, depth = 0 }: { c: Comment; depth?: number }) {
  const [replyOpen, setReplyOpen] = useState(false);
  return (
    <div className="nested-reply" style={depth > 0 ? { marginLeft: `${depth * 12}px` } : undefined}>
      <CommentNode c={c} />
      {(c.replies ?? []).length > 0 && (c.replies ?? []).map((r) => (
        <NestedNode key={r.id} c={r} depth={depth + 1} />
      ))}
      {replyOpen ? (
        <ReplyBox targetId={c.id} onDone={() => setReplyOpen(false)} />
      ) : (
        <button className="reply-link" style={{ fontSize: "0.75em" }} onClick={(e) => { e.stopPropagation(); setReplyOpen(true); }}>Reply</button>
      )}
    </div>
  );
}

function CommentNode({ c, isRoot }: { c: ParsedComment | Comment; isRoot?: boolean }) {
  const editingId = useStore((s) => s.editingId);
  const editingText = useStore((s) => s.editingText);
  const history = useStore((s) => s.history[c.id]);
  const store = useStore();
  const [colorOpen, setColorOpen] = useState(false);
  const [histOpen, setHistOpen] = useState(false);
  const { anchorRef, menuRef, placement } = useMenuPlacement(colorOpen);
  const editing = editingId === c.id;

  // D1: the root comment always owns the highlight color, with or without replies.
  const showColor = !!isRoot;
  const quote = isRoot && "anchor" in c ? c.anchor.quote : "";

  return (
    <div className={`cnode ${isRoot ? "is-root" : "is-reply"} ${c.resolved ? "resolved" : ""}`}>
      <div className="top">
        {showColor && <span className="swatch-sm" style={{ background: SWATCH_VAR[c.color] }} />}
        <span className="auth">{c.author || "Highlight"}</span>
        <span className={`status-tag ${c.resolved ? "done" : "open"}`}>{c.resolved ? "Resolved" : "Open"}</span>
        <span className="time" title={fmtFull(c.timestamp)}>{fmtTime(c.timestamp)}</span>
      </div>

      {isRoot && <div className="quote">“{quote || "(no text)"}”</div>}

      {editing ? (
        <>
          <textarea
            autoFocus
            value={editingText}
            placeholder="Write your comment or change request…"
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => store.setEditingText(e.target.value)}
          />
          <div className="actions">
            <button style={{ borderColor: "var(--accent)", color: "var(--accent)" }} onClick={(e) => { e.stopPropagation(); store.commitEdit(); }}>Save</button>
            <button onClick={(e) => { e.stopPropagation(); store.cancelEdit(); }}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          <div className="ctext">{c.text ? c.text : <span style={{ color: "var(--muted)" }}>— no comment —</span>}</div>
          <div className="actions">
            <button onClick={(e) => { e.stopPropagation(); store.startEdit(c.id); }}>Edit</button>
            {showColor && (
              <div className="color-dd" ref={anchorRef} onClick={(e) => e.stopPropagation()}>
                <button className="cbtn" onClick={() => setColorOpen((v) => !v)}>
                  <span className="swatch-sm" style={{ background: SWATCH_VAR[c.color] }} /> Color
                </button>
                {colorOpen && (
                  <div className={`cmenu${placement.flipX ? " flip-x" : ""}${placement.flipY ? " flip-y" : ""}`} ref={menuRef}>
                    {COLORS.map((col) => (
                      <span
                        key={col}
                        className={`swatch-sm ${col === c.color ? "sel" : ""}`}
                        style={{ background: SWATCH_VAR[col] }}
                        title={col}
                        onClick={() => { store.setColor(c.id, col); setColorOpen(false); }}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
            <button onClick={(e) => { e.stopPropagation(); store.toggleResolve(c.id); }}>
              {c.resolved ? "Reopen" : "Resolve"}
            </button>
            {history && history.length > 0 && (
              <button onClick={(e) => { e.stopPropagation(); setHistOpen((v) => !v); }}>
                History ({history.length})
              </button>
            )}
            <button className="del" onClick={(e) => { e.stopPropagation(); store.deleteComment(c.id); }}>Delete</button>
          </div>

          {histOpen && history && history.length > 0 && (
            <ul className="trace" onClick={(e) => e.stopPropagation()}>
              {history.map((h, i) => (
                <li key={i}>
                  <span className={`status-tag ${h.status === "resolved" ? "done" : "open"}`}>
                    {h.status === "resolved" ? "Resolved" : "Reopened"}
                  </span>
                  <span className="by">{h.author}</span>
                  <span className="at">{fmtFull(h.timestamp)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
