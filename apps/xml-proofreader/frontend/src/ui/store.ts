// ============================================================
// Application store (Zustand).
//
// On Open, the file's content is copied into an in-memory WORKING COPY. All
// annotations modify only this working copy (plus a crash-recovery temp copy);
// the original file on disk is never written. The result is persisted only on
// Export, which writes to a user-chosen file. The app starts empty.
// ============================================================

import { create } from "zustand";
import { createFileSystem, createResource, createStorage } from "../adapters";
import { parseXml } from "../core/xml/parse";
import { detectLanguage, UnsupportedLanguageError } from "../core/lang/registry";
import { isMapRoot, parseMap, mapOutline, type MapModel } from "../core/map/model";
import { buildMergedDoc } from "../core/map/merge";
import { parseComments, type ParsedComment } from "../core/oxygen/parse";
import {
  createAnnotation,
  updateAnnotation,
  deleteAnnotation,
  buildThreadPiGroups,
  type ThreadInput,
  type ReplyInput,
} from "../core/oxygen/serialize";
import type { Comment, HighlightColor } from "../core/model/types";
import type { RenderedDoc } from "../core/render/model";
import type { Issue } from "../core/issues/types";
import { locateQuote, locateQuotePartial, isInsideTag } from "../core/issues/anchor";
import { findingsToIssues } from "../core/issues/fromFindings";
import { mergeIssuesAdditive } from "../core/issues/merge";
import type { Finding } from "../core/findings/types";
import { createLocalProviders } from "../core/issues/providers";
import { isToolAllowed, filterAllowedTools, toolBlockedReason } from "../core/issues/mcp-policy";
import { coerceToolArgs, findDocumentPathParam, type JsonSchema } from "../core/mcp/args";
import type { CommentHistoryEntry, CommentStatus } from "../core/workspace/types";
import { issueDocKey, persistIssues as _persistIssues, restoreIssues as _restoreIssues } from "../core/workspace/issuesStore";
import { isTauri } from "../adapters/tauri/TauriFileSystem";
import type { ChatMessage, ToolCallProposal } from "./chat/types";

const fs = createFileSystem();
const localProviders = createLocalProviders();
const resource = createResource();
const storage = createStorage();
const USER = { name: "Maria Ruiz", initials: "MR" };
const AUTOSAVE_MS = 1200;

export interface SelectionRange {
  start: number;
  end: number;
  quote: string;
}

export interface Toast {
  id: number;
  msg: string;
  icon: string;
}

type ViewMode = "doc" | "xml";
export type RightMode = "comments" | "issues" | "chat" | "proofreader" | "xml";
type Filter = "all" | "open" | "resolved";

/**
 * Derive the default suggested file name for "Save as…" (F8).
 * Preserves the source extension (e.g. .dita → _reviewed.dita).
 * Falls back to .xml for unrecognised / missing extensions.
 * Exported for unit testing only.
 */
export function suggestedSaveName(fileName: string | null, saveUri: string | null): string {
  if (saveUri) return fileName ?? "document";
  const name = fileName || "document";
  const base = name.replace(/\.[^.]+$/, "");
  const ext = name.match(/(\.[^.]+)$/)?.[1] ?? ".xml";
  return `${base}_reviewed${ext}`;
}

/** Derive a display file name from an adapter URI/path. */
function nameFromUri(uri: string, fallback: string): string {
  if (uri.startsWith("fsa:")) return uri.split(":")[1] || fallback;
  if (uri.startsWith("mem:")) return uri.slice(4) || fallback;
  return uri.split(/[\\/]/).pop() || fallback;
}

interface AppState {
  user: typeof USER;
  canSaveInPlace: boolean;

  /** The originally opened file (for reference). Never written to. */
  uri: string | null;
  /** The bound save target, set by Save As / first save. Save overwrites this. */
  saveUri: string | null;
  fileName: string;
  buffer: string;
  rendered: RenderedDoc;
  comments: ParsedComment[];
  dirty: boolean;
  /** Detected structured-content language (e.g. "DITA", "S1000D"). */
  language: string;
  /** Detected version / issue (e.g. "1.3", "4.1"). */
  version: string;
  /** Set when the document language is not supported (names the language). */
  languageError: { name: string; detail: string } | null;
  /** Machine-generated findings (schema/support now; Oxygen MCP & AI in B8/B9). */
  issues: Issue[];
  /** The issue card currently "active" (used to scroll the viewer to the anchor). */
  activeIssueId: string | null;
  /** Set when the open document is a DITA map / S1000D PM. */
  mapModel: MapModel | null;
  /** Whether "Resolve all topics" merged view is active (read-only). */
  merged: boolean;

  viewMode: ViewMode;
  rightMode: RightMode;
  zoom: number;
  filter: Filter;
  search: string;

  activeId: string | null;
  editingId: string | null;
  editingText: string;

  /**
   * Session-scoped state-change history (open ⇄ resolved), keyed by comment id.
   * Oxygen does not persist this in the file (see docs/oxygen-format.md §5), so
   * it lives only for the current session and resets when a document is loaded.
   */
  history: Record<string, CommentHistoryEntry[]>;

  toasts: Toast[];
  lastTs: number;

  // actions
  setAuthor: (name: string, initials: string) => void;
  openFile: () => Promise<void>;
  loadBuffer: (uri: string | null, fileName: string, buffer: string) => void;
  addAnnotation: (range: SelectionRange, color: HighlightColor, withComment: boolean) => void;
  setActive: (id: string | null) => void;
  focusByKey: (key: number) => void;
  setIssues: (issues: Issue[]) => void;
  /** Re-run the local issue providers over the current buffer. Does NOT touch the Oxygen MCP (D7). */
  runProviders: () => Promise<void>;
  /** Explicitly run the Oxygen MCP provider on demand (spawns Oxygen). Merges into store.issues. */
  runOxygenCheck: () => Promise<void>;
  goToIssue: (id: string) => void;
  ignoreIssue: (id: string) => void;
  acceptSuggestion: (id: string, color?: HighlightColor) => void;
  resolveAllTopics: () => Promise<void>;
  collapseMap: () => void;
  openTopicByHref: (href: string) => Promise<void>;
  startEdit: (id: string) => void;
  setEditingText: (text: string) => void;
  commitEdit: () => void;
  cancelEdit: () => void;
  deleteComment: (id: string) => void;
  setColor: (id: string, color: HighlightColor) => void;
  toggleResolve: (id: string) => void;
  /** Add a reply to a comment thread (converts a simple comment into a root). */
  reply: (id: string, text: string) => void;

  save: () => Promise<void>;
  saveAs: () => Promise<void>;
  buildExport: () => string;

  /** True only when running inside Tauri (LlmPort transport available). */
  graderAvailable: boolean;
  /** Run AIGrader with current settings + rules; results go to store.issues. */
  runGrader: () => Promise<void>;

  /** True only when running inside Tauri (chat requires LlmPort + McpPort). */
  chatAvailable: boolean;
  chatMessages: ChatMessage[];
  /** True while a chat completion is in-flight. */
  chatPending: boolean;
  sendChat: (text: string) => Promise<void>;
  /** Run the structured findings pipeline from chat; attaches findings to the reply (D2). */
  detectChatIssues: (instruction: string) => Promise<void>;
  /** Convert findings (from a chat detection reply) into anchored Issues and show the Issues tab. */
  addFindingsToIssues: (findings: Finding[]) => void;
  approveToolCall: (messageId: string, callId: string) => Promise<void>;
  rejectToolCall: (messageId: string, callId: string) => void;
  clearChat: () => void;
  /** Fetch available MCP tools from the Oxygen endpoint. Throws if MCP not available. */
  listMcpTools: () => Promise<import("../ports/McpPort").McpTool[]>;
  /**
   * F4 (ADR-0029): directly invoke an MCP tool without an LLM round-trip.
   * Creates a pending ToolCallProposal in chatMessages and switches to the chat panel.
   * No-op if the tool is not found in the cached tool list.
   */
  directInvokeTool: (toolName: string) => void;

  setView: (m: ViewMode) => void;
  setRight: (m: RightMode) => void;
  setZoom: (delta: number) => void;
  setFilter: (f: Filter) => void;
  setSearch: (s: string) => void;

  toast: (msg: string, icon?: string) => void;
  dismissToast: (id: number) => void;
}

let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
let toastSeq = 1;
let llmPortOverride: import("../ports/LlmPort").LlmPort | null = null;
let chatLlmOverride: import("../ports/LlmPort").LlmPort | null = null;
// Cached MCP tools list, keyed by endpoint. Populated only by an explicit user
// action (listMcpTools / runOxygenCheck). sendChat advertises tools from this
// cache instead of calling listTools() per message, so opening a document or a
// normal chat never spawns Oxygen (D7 / ADR-0018).
let mcpToolsCache: { endpoint: string; tools: import("../ports/McpPort").McpTool[] } | null = null;

interface Recomputed {
  rendered: RenderedDoc;
  comments: ParsedComment[];
  language: string;
  version: string;
  languageError: { name: string; detail: string } | null;
  mapModel: MapModel | null;
}

const EMPTY_RENDER: RenderedDoc = { title: null, subtitle: null, blocks: [], outline: [] };

function placeholderRendered(href: string): RenderedDoc {
  return {
    title: [{ kind: "text", text: href, srcStart: 0 }],
    subtitle: null,
    blocks: [{
      kind: "note", id: `missing-${href}`, src: { start: 0, end: 0 },
      noteType: "warning", label: "Unresolved",
      inlines: [{ kind: "text", text: `Topic not resolved: ${href} (only available in the desktop app).`, srcStart: 0 }],
    }],
    outline: [],
  };
}

/** Navigation view shown when a map/PM is opened (before "Resolve all topics"). */
function navRendered(map: MapModel): RenderedDoc {
  return {
    title: [{ kind: "text", text: map.title, srcStart: 0 }],
    subtitle: [{ kind: "text", text: `${map.kind === "s1000d-pm" ? "S1000D Publication Module" : "DITA map"} — open a topic, or press “Resolve all topics”.`, srcStart: 0 }],
    blocks: [{
      kind: "note", id: "map-hint", src: { start: 0, end: 0 }, noteType: "note", label: "Map",
      inlines: [{ kind: "text", text: `${map.nodes.length} top-level entries. Use the hierarchy on the left to navigate.`, srcStart: 0 }],
    }],
    outline: mapOutline(map.nodes).map((o, i) => ({ id: `mapnode-${i}`, text: o.title, level: o.level, href: o.href })),
  };
}

function recompute(buffer: string): Recomputed {
  const tree = parseXml(buffer);
  const comments = parseComments(tree, buffer);
  try {
    const { detection, profile } = detectLanguage(tree, buffer);
    if (isMapRoot(tree)) {
      const map = parseMap(tree, buffer);
      return {
        rendered: navRendered(map), comments,
        language: detection.language, version: detection.version || "map",
        languageError: null, mapModel: map,
      };
    }
    return {
      rendered: profile.buildRendered(tree, buffer), comments,
      language: detection.language, version: detection.version, languageError: null, mapModel: null,
    };
  } catch (e) {
    if (e instanceof UnsupportedLanguageError) {
      return {
        rendered: EMPTY_RENDER, comments, language: "", version: "",
        languageError: { name: e.detectedName, detail: e.detail }, mapModel: null,
      };
    }
    throw e;
  }
}

// F7 (ADR-0027): fire-and-forget persistence helper — reads userId lazily to
// avoid a circular import at module level (sessionStore imports useStore).
async function persistStoreIssues(
  issues: Issue[],
  uri: string | null,
  buffer: string
): Promise<void> {
  const { useSession } = await import("./sessionStore");
  const userId = useSession.getState().user?.id;
  if (!userId) return;
  await _persistIssues(storage, userId, issueDocKey(uri, buffer), issues);
}

export const useStore = create<AppState>((set, get) => {
  function applyBuffer(buffer: string, opts: { dirty?: boolean } = {}) {
    const { rendered, comments, language, version, languageError, mapModel } = recompute(buffer);
    set({ buffer, rendered, comments, language, version, languageError, mapModel, dirty: opts.dirty ?? get().dirty });
    if (opts.dirty) scheduleAutosave();
  }

  function scheduleAutosave() {
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      const { fileName, buffer } = get();
      fs.saveTemp(`autosave:${fileName}`, buffer).catch(() => {});
    }, AUTOSAVE_MS);
  }

  function uniqueTs(): number {
    const now = Date.now();
    const ts = now <= get().lastTs ? get().lastTs + 1000 : now;
    set({ lastTs: ts });
    return ts;
  }

  /**
   * Locate a comment by id, returning its thread root and (if the id refers to
   * a reply) the reply itself. Replies live nested in `root.replies` and have no
   * own spans — every thread mutation rewrites the whole block via the root.
   */
  function locate(id: string | null): { root: ParsedComment; reply?: Comment } | undefined {
    if (!id) return undefined;
    function findReply(replies: Comment[]): Comment | undefined {
      for (const r of replies) {
        if (r.id === id) return r;
        const found = findReply(r.replies ?? []);
        if (found) return found;
      }
      return undefined;
    }
    for (const root of get().comments) {
      if (root.id === id) return { root };
      const reply = findReply(root.replies ?? []);
      if (reply) return { root, reply };
    }
    return undefined;
  }

  function isThread(c: ParsedComment): boolean {
    return Array.isArray(c.replies) && c.replies.length > 0;
  }

  /** Generate an Oxygen-style root id, e.g. "q52_qnb_qjc" (three groups of three). */
  function genThreadId(): string {
    const g = () => Math.random().toString(36).slice(2, 5).padEnd(3, "x");
    return `${g()}_${g()}_${g()}`;
  }

  function rootInputOf(root: ParsedComment, id: string): ThreadInput["root"] {
    return {
      author: root.author, timestamp: root.timestamp, text: root.text,
      color: root.color, resolved: root.resolved, id,
    };
  }

  function replyInputOf(r: Comment, parentId: string, mid: number): ReplyInput {
    // Preserve the Oxygen id of a reply when it has nested replies (for parentID lookups).
    const oxyId = r.id && !r.id.startsWith("c:") ? r.id : undefined;
    return { author: r.author, timestamp: r.timestamp, text: r.text, parentId, mid, resolved: r.resolved, id: oxyId };
  }

  /** Walk the reply tree depth-first and return all replies in opening (mid-ascending) order. */
  function flattenReplies(replies: Comment[]): Comment[] {
    const out: Comment[] = [];
    function walk(rs: Comment[]) {
      for (const r of rs) {
        out.push(r);
        walk(r.replies ?? []);
      }
    }
    walk(replies);
    return out;
  }

  /** Build ReplyInput list from a thread's reply tree, preserving original mids and parentIds. */
  function buildReplyInputs(root: ParsedComment, rootId: string): ReplyInput[] {
    const all = flattenReplies(root.replies ?? []);
    return all.map((r, i) => {
      const mid = r.mid ?? (i + 1);
      const parentId = r.parentId ?? rootId;
      return replyInputOf(r, parentId, mid);
    });
  }

  /**
   * Rewrite a thread's full PI block (root + all replies) non-destructively,
   * preserving the shared annotated text. This is the thread-aware counterpart
   * of `updateAnnotation`; using `buildPiGroups` on a thread root would drop the
   * replies (see ADR-0007).
   */
  function writeThread(root: ParsedComment, t: ThreadInput): string {
    const { open, close } = buildThreadPiGroups(t);
    const buffer = get().buffer;
    const inner = buffer.slice(root.spans.contentStart, root.spans.contentEnd);
    return buffer.slice(0, root.spans.openStart) + open + inner + close + buffer.slice(root.spans.closeEnd);
  }

  function recordHistory(id: string, status: CommentStatus): void {
    const entry: CommentHistoryEntry = { status, timestamp: Date.now(), author: get().user.name };
    set((s) => ({ history: { ...s.history, [id]: [...(s.history[id] ?? []), entry] } }));
  }

  return {
    user: USER,
    canSaveInPlace: fs.canSaveInPlace,
    uri: null,
    saveUri: null,
    fileName: "",
    buffer: "",
    rendered: { title: null, subtitle: null, blocks: [], outline: [] },
    comments: [],
    dirty: false,
    language: "",
    version: "",
    languageError: null,
    issues: [],
    activeIssueId: null,
    mapModel: null,
    merged: false,
    viewMode: "doc",
    rightMode: "comments",
    zoom: 100,
    filter: "all",
    search: "",
    activeId: null,
    editingId: null,
    editingText: "",
    history: {},
    toasts: [],
    lastTs: 0,
    graderAvailable: isTauri(),
    chatAvailable: isTauri(),
    chatMessages: [],
    chatPending: false,

    setAuthor: (name, initials) => set({ user: { name, initials } }),

    openFile: async () => {
      const file = await fs.openFile();
      if (!file) return;
      get().loadBuffer(file.uri, file.fileName, file.content);
      get().toast(`Opened ${file.fileName}`, "📄");
    },

    loadBuffer: (uri, fileName, buffer) => {
      const { rendered, comments, language, version, languageError, mapModel } = recompute(buffer);
      // Opening does NOT bind a save target — the original is never overwritten.
      set({
        uri, saveUri: null, fileName, buffer, rendered, comments, language, version, languageError, mapModel,
        merged: false, dirty: false, activeId: null, editingId: null, editingText: "", history: {},
        issues: [], activeIssueId: null,
      });
      // F7: restore persisted issues concurrently with runProviders. Both use
      // mergeIssuesAdditive so they don't overwrite each other regardless of order.
      void (async () => {
        const { useSession } = await import("./sessionStore");
        const userId = useSession.getState().user?.id;
        if (!userId || get().buffer !== buffer) return;
        const restored = await _restoreIssues(
          storage, userId, issueDocKey(uri, buffer), buffer
        );
        if (!restored.length || get().buffer !== buffer) return;
        // G3: mergeIssuesAdditive is now strictly additive — a single call suffices.
        set((s) => ({ issues: mergeIssuesAdditive(s.issues, restored) }));
      })();
      void get().runProviders();
    },

    addAnnotation: (range, color, withComment) => {
      const ts = uniqueTs();
      const buffer = createAnnotation(get().buffer, range.start, range.end, {
        author: get().user.name,
        timestamp: ts,
        text: "",
        color,
        resolved: false,
        forceComment: withComment,
      });
      applyBuffer(buffer, { dirty: true });
      // The new annotation's opening PI starts exactly at range.start.
      const created = get().comments.find((c) => c.spans.openStart === range.start);
      if (created) {
        set({ activeId: created.id, rightMode: "comments" });
        if (withComment) get().startEdit(created.id);
        else get().toast("Highlight added", "✓");
      }
    },

    setActive: (id) => set({ activeId: id }),
    setIssues: (issues) => set({ issues }),

    runProviders: async () => {
      const buffer = get().buffer;
      if (!buffer) return;
      const all: Issue[] = [];

      // Local providers (always available — no Tauri dep). The Oxygen MCP
      // provider is deliberately NOT run here: spawning Oxygen on every document
      // load is expensive and must be on-demand only (D7). Use runOxygenCheck().
      for (const p of localProviders) {
        if (p.isAvailable()) {
          const found = await p.run(buffer).catch(() => [] as Issue[]);
          all.push(...found);
        }
      }

      // Guard against a document being replaced while providers were running.
      // F7: additive merge so restored issues from other sources are preserved.
      if (get().buffer === buffer) set((s) => ({ issues: mergeIssuesAdditive(s.issues, all) }));
    },

    runOxygenCheck: async () => {
      const buffer = get().buffer;
      if (!buffer) return;
      // Settings are read lazily (same pattern as runGrader) to avoid a circular
      // dep at module level.
      const { useSession } = await import("./sessionStore");
      const { oxygenMcpEndpoint } = useSession.getState().settings.ai;
      const { makeTauriMcp } = await import("../adapters/tauri/TauriMcp");
      const { OxygenIssueProvider } = await import("../core/issues/providers/oxygen");
      const mcp = makeTauriMcp(() => oxygenMcpEndpoint);
      const oxygenProvider = new OxygenIssueProvider(mcp);
      if (!oxygenProvider.isAvailable()) {
        get().toast("Oxygen MCP not configured (see Settings → AI & MCP)", "⚠");
        return;
      }
      const found = await oxygenProvider.run(buffer).catch(() => [] as Issue[]);
      // Prime the tools cache so subsequent chats can advertise tools without
      // re-spawning Oxygen. Only read-only tools are cached/advertised (D9).
      mcp.listTools().then((tools) => {
        mcpToolsCache = { endpoint: oxygenMcpEndpoint, tools: filterAllowedTools(tools) };
      }).catch(() => {});
      // Guard against a document being replaced while the provider was running,
      // and replace any prior Oxygen issues (avoid duplicates on re-run).
      if (get().buffer === buffer) {
        set((s) => ({ issues: [...s.issues.filter((x) => x.source !== "oxygen"), ...found] }));
        // F7: persist so Oxygen findings survive a reload.
        const { uri, buffer: buf } = get();
        void persistStoreIssues(get().issues, uri, buf);
      }
    },

    goToIssue: (id) => {
      set({ activeIssueId: id, rightMode: "issues" });
    },

    ignoreIssue: (id) => {
      set((s) => ({ issues: s.issues.filter((x) => x.id !== id) }));
      // F7: persist so the dismissal survives a reload.
      const { uri, buffer } = get();
      void persistStoreIssues(get().issues, uri, buffer);
    },

    acceptSuggestion: (id, color = "yellow") => {
      const { issues, buffer } = get();
      const issue = issues.find((x) => x.id === id);
      if (!issue?.suggestion) return;

      // G2 (ADR-0032): cascading anchor resolution — never hard-blocks.
      // Level 1: locateQuote covers exact, whitespace-normalized, case-insensitive,
      //          and entity/typographic-normalized tiers.
      // Level 2: locateQuotePartial — longest safe prefix of quote tokens.
      // Level 3: stored issue.anchor (if it exists and the span is safe to splice).
      // If nothing works, toast a clear message and return (no mutation).
      let startOffset: number;
      let endOffset: number;
      let approximate = false;

      const m = issue.quote ? locateQuote(buffer, issue.quote) : undefined;
      if (m) {
        startOffset = m.startOffset;
        endOffset = m.endOffset;
      } else {
        const partial = issue.quote ? locateQuotePartial(buffer, issue.quote) : undefined;
        if (partial) {
          startOffset = partial.startOffset;
          endOffset = partial.endOffset;
          approximate = true;
        } else if (issue.anchor) {
          // Use the stored anchor only when the source span is safe (no tag in range).
          const span = buffer.slice(issue.anchor.startOffset, issue.anchor.endOffset);
          if (!span.includes("<") && !span.includes(">") && span.length > 0 && !isInsideTag(buffer, issue.anchor.startOffset)) {
            startOffset = issue.anchor.startOffset;
            endOffset = issue.anchor.endOffset;
            approximate = true;
          } else {
            get().toast("Cannot apply: quoted text could not be located safely in the document", "⚠");
            return;
          }
        } else {
          get().toast("Cannot apply: no locatable anchor for this suggestion", "⚠");
          return;
        }
      }

      if (approximate) {
        get().toast("Approximate anchor — comment created on the nearest matching text", "⚠");
      }

      // E3 (ADR-0020, supersedes ADR-0015; restores ADR-0003): creates a standard
      // comment carrying the suggestion — does NOT edit the document text.
      const text = `${issue.message} — Sugerencia: ${issue.suggestion}`;
      const newBuffer = createAnnotation(buffer, startOffset, endOffset, {
        author: get().user.name,
        timestamp: uniqueTs(),
        text,
        color, // F2: caller passes defaultHighlight from sessionStore (E-Q1 default).
        resolved: false,
        forceComment: true,
      });
      applyBuffer(newBuffer, { dirty: true });
      set((s) => ({ issues: s.issues.filter((x) => x.id !== id) }));
      // F7: persist so the accepted issue is removed from the saved list.
      const { uri, buffer: buf } = get();
      void persistStoreIssues(get().issues, uri, buf);
      // Activate the freshly created comment (its opening PI starts exactly at startOffset).
      const created = get().comments.find((c) => c.spans.openStart === startOffset);
      if (created) set({ activeId: created.id, rightMode: "comments" });
      if (!approximate) get().toast("Suggestion added as a comment", "✓");
    },

    resolveAllTopics: async () => {
      const { mapModel, uri } = get();
      if (!mapModel) return;
      const provide = async (href: string): Promise<string | null> => {
        const bytes = await resource.readBytes(uri, href).catch(() => null);
        return bytes ? new TextDecoder().decode(bytes) : null;
      };
      const merged = await buildMergedDoc(mapModel, provide);
      set({ rendered: merged, merged: true, activeId: null });
      get().toast("Resolved all topics — merged view", "🧩");
    },

    collapseMap: () => {
      const { mapModel } = get();
      if (!mapModel) return;
      set({ rendered: navRendered(mapModel), merged: false });
    },

    openTopicByHref: async (href) => {
      const { uri, mapModel } = get();
      if (!mapModel) return;
      const bytes = await resource.readBytes(uri, href).catch(() => null);
      let rendered: RenderedDoc;
      let resolved = false;
      if (bytes) {
        const text = new TextDecoder().decode(bytes);
        try {
          const tree = parseXml(text);
          const { profile } = detectLanguage(tree, text);
          rendered = profile.buildRendered(tree, text);
          resolved = true;
        } catch {
          rendered = placeholderRendered(href);
        }
      } else {
        rendered = placeholderRendered(href);
      }
      set({ rendered, merged: false, activeId: null });
      const name = href.split("/").pop() ?? href;
      if (resolved) get().toast(`Opened ${name}`, "📄");
      else get().toast(`${name} not available in the browser`, "🛈");
    },

    focusByKey: (key) => {
      const c = get().comments.find((x) => x.key === key);
      if (c) set({ activeId: c.id, rightMode: "comments" });
    },

    startEdit: (id) => {
      const loc = locate(id);
      if (!loc) return;
      // Convert a comment-less highlight into a comment so it gains a stable id.
      if (id.startsWith("h:")) {
        const root = loc.root;
        const buffer = updateAnnotation(get().buffer, root.spans, {
          author: get().user.name, timestamp: uniqueTs(), text: "",
          color: root.color, resolved: false, forceComment: true,
        });
        applyBuffer(buffer, { dirty: true });
        const c = get().comments.find((x) => x.spans.openStart === root.spans.openStart)
          ?? get().comments.find((x) => x.text === "" && x.color === root.color);
        if (!c) return;
        set({ editingId: c.id, editingText: c.text, activeId: c.id });
        return;
      }
      const target = loc.reply ?? loc.root;
      set({ editingId: target.id, editingText: target.text, activeId: loc.root.id });
    },

    setEditingText: (text) => {
      const loc = locate(get().editingId);
      if (!loc) {
        set({ editingText: text });
        return;
      }
      const { root, reply } = loc;
      let buffer: string;
      if (isThread(root)) {
        const replies = buildReplyInputs(root, root.id);
        if (reply) {
          // Find by matching author+timestamp+mid (stable across text edits).
          const idx = replies.findIndex((r) => r.author === reply.author && r.timestamp === reply.timestamp && r.mid === reply.mid);
          if (idx >= 0) replies[idx] = { ...replies[idx], text };
        }
        const t: ThreadInput = {
          root: reply ? rootInputOf(root, root.id) : { ...rootInputOf(root, root.id), text },
          replies,
          highlight: root.hasHighlight ? root.color : undefined,
        };
        buffer = writeThread(root, t);
      } else {
        buffer = updateAnnotation(get().buffer, root.spans, {
          author: root.author, timestamp: root.timestamp, text, color: root.color, resolved: root.resolved,
        });
      }
      applyBuffer(buffer, { dirty: true });
      // id is stable across text edits (author/timestamp/mid unchanged).
      set({ editingText: text });
    },

    commitEdit: () => {
      set({ editingId: null, editingText: "" });
      get().toast("Comment saved", "✓");
    },

    cancelEdit: () => set({ editingId: null, editingText: "" }),

    deleteComment: (id) => {
      const loc = locate(id);
      if (!loc) return;
      const { root, reply } = loc;
      let buffer: string;
      if (reply) {
        // Collect ids of the deleted reply and all its descendants, then filter them out.
        const deletedIds = new Set<string>();
        const collectIds = (c: Comment) => { deletedIds.add(c.id); (c.replies ?? []).forEach(collectIds); };
        collectIds(reply);
        // Map from Comment.id to its mid for filtering.
        const allReplies = flattenReplies(root.replies ?? []);
        const idToMid = new Map(allReplies.map((c) => [c.id, c.mid]));
        const deletedMids = new Set(Array.from(deletedIds).map((cid) => idToMid.get(cid)).filter(Boolean) as number[]);
        const remaining = buildReplyInputs(root, root.id).filter((r) => !deletedMids.has(r.mid));
        const t: ThreadInput = {
          root: rootInputOf(root, root.id),
          replies: remaining,
          highlight: root.hasHighlight ? root.color : undefined,
        };
        buffer = writeThread(root, t);
      } else {
        // Deleting a root removes the whole thread block (replies included).
        buffer = deleteAnnotation(get().buffer, root.spans);
      }
      applyBuffer(buffer, { dirty: true });
      set((s) => ({
        activeId: s.activeId === id ? null : s.activeId,
        editingId: s.editingId === id ? null : s.editingId,
      }));
      get().toast("Comment deleted", "🗑");
    },

    setColor: (id, color) => {
      const loc = locate(id);
      if (!loc || loc.reply) return;
      const root = loc.root;
      let buffer: string;
      if (isThread(root)) {
        // Recolor a thread root: re-emit wrapper with the new color (always emit on explicit recolor).
        const replies = root.replies!.map((r, i) => replyInputOf(r, root.id, i + 1));
        buffer = writeThread(root, {
          root: rootInputOf(root, root.id),
          replies,
          highlight: color,
        });
      } else {
        buffer = updateAnnotation(get().buffer, root.spans, {
          author: root.author, timestamp: root.timestamp, text: root.text,
          color, resolved: root.resolved, forceComment: root.text.trim() === "" && id.startsWith("c:"),
        });
      }
      applyBuffer(buffer, { dirty: true });
    },

    toggleResolve: (id) => {
      const loc = locate(id);
      if (!loc) return;
      const { root, reply } = loc;
      let buffer: string;
      let newStatus: boolean;
      if (isThread(root)) {
        const replies = buildReplyInputs(root, root.id);
        let rootResolved = root.resolved;
        if (reply) {
          const idx = replies.findIndex((r) => r.author === reply.author && r.timestamp === reply.timestamp && r.mid === reply.mid);
          if (idx >= 0) {
            newStatus = !replies[idx].resolved;
            replies[idx] = { ...replies[idx], resolved: newStatus };
          } else {
            newStatus = !reply.resolved;
          }
        } else {
          newStatus = !root.resolved;
          rootResolved = newStatus;
        }
        const t: ThreadInput = {
          root: { ...rootInputOf(root, root.id), resolved: rootResolved },
          replies,
          highlight: root.hasHighlight ? root.color : undefined,
        };
        buffer = writeThread(root, t);
      } else {
        newStatus = !root.resolved;
        buffer = updateAnnotation(get().buffer, root.spans, {
          author: root.author, timestamp: root.timestamp, text: root.text,
          color: root.color, resolved: newStatus,
          forceComment: root.text.trim() === "" && id.startsWith("c:"),
        });
      }
      recordHistory(id, newStatus ? "resolved" : "open");
      applyBuffer(buffer, { dirty: true });
    },

    reply: (id, text) => {
      const loc = locate(id);
      if (!loc || !text.trim()) return;
      const { root, reply: replyTarget } = loc;
      const wasThread = isThread(root);
      const rootId = wasThread ? root.id : genThreadId();
      const replies = buildReplyInputs(root, rootId);

      // Determine parentId for the new reply. If the target is a reply with a synthetic
      // id (starts with "c:"), mint a real Oxygen id for it so parentID round-trips correctly.
      let newParentId: string;
      if (replyTarget) {
        const needsMintedId = !replyTarget.id || replyTarget.id.startsWith("c:");
        if (needsMintedId) {
          const mintedId = genThreadId();
          const idx = replies.findIndex(
            (r) => r.author === replyTarget.author && r.timestamp === replyTarget.timestamp && r.mid === replyTarget.mid
          );
          if (idx >= 0) replies[idx] = { ...replies[idx], id: mintedId };
          newParentId = mintedId;
        } else {
          newParentId = replyTarget.id;
        }
      } else {
        newParentId = rootId;
      }

      const nextMid = replies.reduce((max, r) => Math.max(max, r.mid), 0) + 1;
      const ts = uniqueTs();
      replies.push({
        author: get().user.name, timestamp: ts, text,
        parentId: newParentId, mid: nextMid, resolved: false,
      });
      const buffer = writeThread(root, { root: rootInputOf(root, rootId), replies, highlight: root.hasHighlight ? root.color : undefined });
      // A simple comment just became a thread root with a new id — carry over any
      // session history recorded against the old id.
      if (!wasThread && rootId !== root.id) {
        set((s) => {
          const prev = s.history[root.id];
          if (!prev) return {} as Partial<AppState>;
          const next = { ...s.history };
          delete next[root.id];
          next[rootId] = prev;
          return { history: next };
        });
      }
      applyBuffer(buffer, { dirty: true });
      set({ activeId: rootId, rightMode: "comments" });
      get().toast("Reply added", "💬");
    },

    buildExport: () => get().buffer,

    // Save: overwrite the bound target file (no dialog). If none is bound yet
    // (nothing exported/saved-as so far), fall back to Save As. The originally
    // opened file is never the bound target, so it is never overwritten.
    save: async () => {
      const { saveUri, fileName, buffer } = get();
      if (!buffer) {
        get().toast("Open a document first", "🛈");
        return;
      }
      if (!saveUri) {
        await get().saveAs();
        return;
      }
      await fs.saveFile(saveUri, fileName, buffer);
      await fs.clearTemp(`autosave:${fileName}`).catch(() => {});
      set({ dirty: false });
      get().toast("Saved", "💾");
    },

    // Save As / Export: write to a user-chosen file and bind it as the new
    // save target, so subsequent Saves overwrite it directly.
    saveAs: async () => {
      const { saveUri, fileName, buffer } = get();
      if (!buffer) {
        get().toast("Open a document first", "🛈");
        return;
      }
      const suggested = suggestedSaveName(fileName, saveUri);
      const uri = await fs.saveFileAs(suggested, buffer);
      if (uri) {
        await fs.clearTemp(`autosave:${fileName}`).catch(() => {});
        set({ saveUri: uri, fileName: nameFromUri(uri, suggested), dirty: false });
        get().toast("Saved as " + nameFromUri(uri, suggested), "⤒");
      }
    },

    runGrader: async () => {
      const { AIGrader } = await import("../core/grader/AIGrader");
      // Settings are read from sessionStore at call time (avoids circular dep at module level).
      const { useSession } = await import("./sessionStore");
      const settings = useSession.getState().settings;
      // llmPortOverride is set by the E2E test seam (window.__docreview.__grader.mock).
      // In production it is always null and the Tauri adapter is used instead.
      let llm = llmPortOverride;
      if (!llm) {
        const { makeLlmPortFromSettings } = await import("../adapters/tauri/TauriLlm");
        llm = makeLlmPortFromSettings(settings.ai);
      }
      const grader = new AIGrader(
        llm!,
        () => useSession.getState().settings.graderRules,
        () => useSession.getState().settings.ai.model
      );
      get().toast("Running AI Proofreader…", "🤖");
      try {
        const newIssues = await grader.run(get().buffer);
        // F6 (ADR-0026): additive — never wipe issues from other sources; dedupe
        // by (source, message, quote) so re-running doesn't accumulate duplicates.
        set((s) => ({
          issues: mergeIssuesAdditive(s.issues, newIssues),
        }));
        // F7: persist so proofreader findings survive a reload.
        const { uri, buffer: buf } = get();
        void persistStoreIssues(get().issues, uri, buf);
        get().toast(`Proofreading complete — ${newIssues.length} finding(s)`, "✓");
      } catch (e) {
        get().toast("Proofreader error: " + (e instanceof Error ? e.message : String(e)), "✗");
      }
    },

    clearChat: () => set({ chatMessages: [], chatPending: false }),

    listMcpTools: async () => {
      const { useSession } = await import("./sessionStore");
      const { oxygenMcpEndpoint } = useSession.getState().settings.ai;
      const { makeTauriMcp } = await import("../adapters/tauri/TauriMcp");
      const mcp = makeTauriMcp(() => oxygenMcpEndpoint);
      if (!mcp.isAvailable()) throw new Error("MCP endpoint not configured");
      // Only ever expose read-only tools (D9): mutating tools are not advertised.
      const tools = filterAllowedTools(await mcp.listTools());
      // Cache so sendChat can advertise tools without spawning Oxygen again (D7).
      mcpToolsCache = { endpoint: oxygenMcpEndpoint, tools };
      return tools;
    },

    directInvokeTool: (toolName: string) => {
      const tool = mcpToolsCache?.tools.find((t) => t.name === toolName);
      const schema = tool?.inputSchema as import("../core/mcp/args").JsonSchema | undefined;
      const msgId = crypto.randomUUID();
      const callId = crypto.randomUUID();
      const proposal: ToolCallProposal = {
        id: callId,
        toolName,
        args: coerceToolArgs({}, schema),
        status: "pending",
      };
      const msg: ChatMessage = {
        id: msgId,
        role: "assistant",
        text: `Run: **${toolName}**`,
        toolCalls: [proposal],
        timestamp: Date.now(),
      };
      set((s) => ({ chatMessages: [...s.chatMessages, msg], rightMode: "chat" }));
    },

    sendChat: async (text: string) => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        text,
        toolCalls: [],
        timestamp: Date.now(),
      };
      set((s) => ({ chatMessages: [...s.chatMessages, userMsg], chatPending: true }));
      try {
        const { useSession } = await import("./sessionStore");
        const settings = useSession.getState().settings;
        let llm = chatLlmOverride;
        if (!llm) {
          const { makeLlmPortFromSettings } = await import("../adapters/tauri/TauriLlm");
          llm = makeLlmPortFromSettings(settings.ai);
        }
        const buffer = get().buffer;

        // Advertise available MCP tools so the model knows it can propose tool
        // calls. We read from the cache ONLY — never call listTools() here, since
        // that would spawn Oxygen on every chat message (D7). The cache is filled
        // by an explicit user action (listMcpTools / runOxygenCheck).
        let toolsSection = "";
        if (isTauri() && mcpToolsCache && mcpToolsCache.tools.length > 0) {
          const { useSession: useSessionInner } = await import("./sessionStore");
          const { oxygenMcpEndpoint } = useSessionInner.getState().settings.ai;
          if (mcpToolsCache.endpoint === oxygenMcpEndpoint) {
            // E5c (ADR-0023): advertise each tool's inputSchema so the model
            // emits well-formed args (object, right fields/types).
            const toolList = mcpToolsCache.tools.map((t) => {
              const schema = t.inputSchema ? `\n  input schema: ${JSON.stringify(t.inputSchema)}` : "";
              return `- ${t.name}: ${t.description ?? ""}${schema}`;
            }).join("\n");
            toolsSection = `\n\nAvailable MCP tools (propose with <tool_call>{"tool":"name","args":{...}}</tool_call>):\n${toolList}`;
          }
        }

        const system = buffer
          ? `You are a helpful assistant reviewing a DITA/XML document. The current document content is:\n\n${buffer.slice(0, 8000)}${toolsSection}`
          : `You are a helpful assistant reviewing DITA/XML documents.${toolsSection}`;
        const req: import("../ports/LlmPort").LlmRequest = {
          system,
          content: text,
          model: settings.ai.model,
          maxTokens: 2048,
        };
        const stripRe = /<tool_call>[\s\S]*?<\/tool_call>/g;
        // Parse <tool_call>...</tool_call> tags from the FULL response (semantics
        // unchanged — done once, after streaming completes).
        const parseToolCalls = (raw: string): ToolCallProposal[] => {
          const re = /<tool_call>([\s\S]*?)<\/tool_call>/g;
          const out: ToolCallProposal[] = [];
          let m: RegExpExecArray | null;
          while ((m = re.exec(raw)) !== null) {
            try {
              const parsed = JSON.parse(m[1]) as { tool: string; args?: Record<string, unknown> };
              out.push({ id: crypto.randomUUID(), toolName: parsed.tool, args: parsed.args ?? {}, status: "pending" });
            } catch {
              // malformed tool_call block — ignore
            }
          }
          return out;
        };

        // E4 (ADR-0022, E-Q3 = free chat only): stream the reply token-by-token
        // when the provider supports it (Tauri). A single assistant bubble is
        // created on the first delta and updated in place. Mocks/browser have no
        // completeStream → plain blocking complete (unchanged behaviour).
        if (llm.completeStream) {
          const assistantId = crypto.randomUUID();
          let acc = "";
          let created = false;
          try {
            const final = await llm.completeStream(req, (delta) => {
              acc += delta;
              const shown = acc.replace(stripRe, "");
              if (!created) {
                created = true;
                set((s) => ({
                  chatMessages: [...s.chatMessages, { id: assistantId, role: "assistant", text: shown, toolCalls: [], timestamp: Date.now() }],
                }));
              } else {
                set((s) => ({ chatMessages: s.chatMessages.map((m) => (m.id === assistantId ? { ...m, text: shown } : m)) }));
              }
            });
            acc = final;
          } catch {
            // Stream failed — fall back to a single blocking completion (may
            // throw → handled by the outer catch).
            acc = await llm.complete(req);
          }
          const toolCalls = parseToolCalls(acc);
          const displayText = acc.replace(stripRe, "").trim();
          if (created) {
            set((s) => ({
              chatMessages: s.chatMessages.map((m) => (m.id === assistantId ? { ...m, text: displayText, toolCalls } : m)),
              chatPending: false,
            }));
          } else {
            set((s) => ({
              chatMessages: [...s.chatMessages, { id: assistantId, role: "assistant", text: displayText, toolCalls, timestamp: Date.now() }],
              chatPending: false,
            }));
          }
        } else {
          const rawResponse = await llm.complete(req);
          const assistantMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: "assistant",
            text: rawResponse.replace(stripRe, "").trim(),
            toolCalls: parseToolCalls(rawResponse),
            timestamp: Date.now(),
          };
          set((s) => ({ chatMessages: [...s.chatMessages, assistantMsg], chatPending: false }));
        }
      } catch (e) {
        set((s) => ({
          chatPending: false,
          chatMessages: [
            ...s.chatMessages,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              text: "Error: " + (e instanceof Error ? e.message : String(e)),
              toolCalls: [],
              timestamp: Date.now(),
            },
          ],
        }));
      }
    },

    detectChatIssues: async (instruction: string) => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(), role: "user", text: instruction, toolCalls: [], timestamp: Date.now(),
      };
      set((s) => ({ chatMessages: [...s.chatMessages, userMsg], chatPending: true }));
      try {
        const { useSession } = await import("./sessionStore");
        const settings = useSession.getState().settings;
        let llm = chatLlmOverride;
        if (!llm) {
          const { makeLlmPortFromSettings } = await import("../adapters/tauri/TauriLlm");
          llm = makeLlmPortFromSettings(settings.ai);
        }
        // Reuse the proofreader's structured prompt (findings schema with
        // replacement, jsonMode) with the chat instruction as the single rule.
        const { buildGraderRequest } = await import("../core/grader/prompt");
        const req = buildGraderRequest([instruction], get().buffer, settings.ai.model);
        const text = await llm.complete(req);
        const { parseFindings } = await import("../core/findings/parse");
        const { findings, error } = parseFindings(text);
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          text: error
            ? `Couldn't extract issues: ${error}`
            : findings.length
              ? `Found ${findings.length} issue${findings.length === 1 ? "" : "s"}:`
              : "No issues found.",
          toolCalls: [],
          findings: error ? undefined : findings,
          timestamp: Date.now(),
        };
        set((s) => ({ chatMessages: [...s.chatMessages, assistantMsg], chatPending: false }));
      } catch (e) {
        set((s) => ({
          chatPending: false,
          chatMessages: [
            ...s.chatMessages,
            { id: crypto.randomUUID(), role: "assistant", text: "Error: " + (e instanceof Error ? e.message : String(e)), toolCalls: [], timestamp: Date.now() },
          ],
        }));
      }
    },

    addFindingsToIssues: (findings: Finding[]) => {
      if (!findings.length) return;
      const added = findingsToIssues(findings, get().buffer);
      set((s) => ({ issues: [...s.issues, ...added], rightMode: "issues" }));
      const { uri, buffer } = get();
      void persistStoreIssues(get().issues, uri, buffer);
      get().toast(`Sent ${added.length} issue${added.length === 1 ? "" : "s"} to Issues`, "✓");
    },

    approveToolCall: async (messageId: string, callId: string) => {
      // Mark as approved optimistically, then execute via MCP.
      set((s) => ({
        chatMessages: s.chatMessages.map((msg) =>
          msg.id !== messageId ? msg : {
            ...msg,
            toolCalls: msg.toolCalls.map((tc) =>
              tc.id !== callId ? tc : { ...tc, status: "approved" as const }
            ),
          }
        ),
      }));
      const { useSession } = await import("./sessionStore");
      const { oxygenMcpEndpoint } = useSession.getState().settings.ai;
      const { makeTauriMcp } = await import("../adapters/tauri/TauriMcp");
      const mcp = makeTauriMcp(() => oxygenMcpEndpoint);
      const msg = get().chatMessages.find((m) => m.id === messageId);
      const tc = msg?.toolCalls.find((c) => c.id === callId);
      if (!tc) return;
      // Read-only guardrail (D9): never execute a mutating tool, even if the
      // model proposed it and the user clicked approve. Block + surface why.
      if (!isToolAllowed(tc.toolName)) {
        const reason = toolBlockedReason(tc.toolName);
        get().toast(reason, "⛔");
        set((s) => ({
          chatMessages: s.chatMessages.map((m2) =>
            m2.id !== messageId ? m2 : {
              ...m2,
              toolCalls: m2.toolCalls.map((c) =>
                c.id !== callId ? c : { ...c, status: "rejected" as const, error: reason }
              ),
            }
          ),
        }));
        return;
      }
      try {
        // E5b (ADR-0023): coerce args (a model may emit them as a JSON string)
        // and light-validate against the tool's advertised inputSchema.
        const schema =
          mcpToolsCache && mcpToolsCache.endpoint === oxygenMcpEndpoint
            ? (mcpToolsCache.tools.find((t) => t.name === tc.toolName)?.inputSchema as JsonSchema | undefined)
            : undefined;
        const args = coerceToolArgs(tc.args, schema);
        // E5a (ADR-0019): point a doc-reading tool at a temp COPY of the buffer
        // (never the original file or its save target). Only when the schema
        // declares a path param the model didn't already fill.
        const docParam = findDocumentPathParam(schema);
        if (isTauri() && docParam && args[docParam] == null && get().buffer) {
          const { writeTempDoc } = await import("../adapters/tauri/TauriMcp");
          args[docParam] = await writeTempDoc(get().buffer);
        }
        const result = await mcp.callTool(tc.toolName, args);
        const resultText = result.content.map((b) => b.text ?? "").join("\n");
        set((s) => ({
          chatMessages: s.chatMessages.map((m2) =>
            m2.id !== messageId ? m2 : {
              ...m2,
              toolCalls: m2.toolCalls.map((c) =>
                c.id !== callId ? c : { ...c, result: resultText }
              ),
            }
          ),
        }));
      } catch (e) {
        set((s) => ({
          chatMessages: s.chatMessages.map((m2) =>
            m2.id !== messageId ? m2 : {
              ...m2,
              toolCalls: m2.toolCalls.map((c) =>
                c.id !== callId ? c : { ...c, error: e instanceof Error ? e.message : String(e) }
              ),
            }
          ),
        }));
      }
    },

    rejectToolCall: (messageId: string, callId: string) => {
      // Invariant: rejectToolCall NEVER calls MCP. It only updates state.
      set((s) => ({
        chatMessages: s.chatMessages.map((msg) =>
          msg.id !== messageId ? msg : {
            ...msg,
            toolCalls: msg.toolCalls.map((tc) =>
              tc.id !== callId ? tc : { ...tc, status: "rejected" as const }
            ),
          }
        ),
      }));
    },

    setView: (m) => set({ viewMode: m }),
    setRight: (m) => set({ rightMode: m }),
    setZoom: (delta) =>
      set((s) => ({ zoom: Math.max(70, Math.min(150, s.zoom + delta * 10)) })),
    setFilter: (f) => set({ filter: f }),
    setSearch: (s2) => set({ search: s2 }),

    toast: (msg, icon = "✓") => {
      const id = toastSeq++;
      set((s) => ({ toasts: [...s.toasts, { id, msg, icon }] }));
      setTimeout(() => get().dismissToast(id), 2400);
    },
    dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  };
});

// Small hook for E2E tests and debugging: load XML content programmatically
// without going through the native file picker.
if (typeof window !== "undefined") {
  (window as unknown as {
    __docreview?: {
      load: (fileName: string, xml: string) => void;
      __grader: {
        enable: () => void;
        mock: (responseJson: string) => void;
        reset: () => void;
      };
      __chat: {
        enable: () => void;
        mock: (responseJson: string) => void;
        mockStream: (responseJson: string, chunks?: number) => void;
        reset: () => void;
        setMcpCache: (endpoint: string, tools: import("../ports/McpPort").McpTool[]) => void;
      };
    };
  }).__docreview = {
    load: (fileName: string, xml: string) =>
      useStore.getState().loadBuffer(null, fileName, xml),
    __grader: {
      enable: () => useStore.setState({ graderAvailable: true }),
      mock: (responseJson: string) => {
        llmPortOverride = { isAvailable: () => true, complete: async () => responseJson };
      },
      reset: () => { llmPortOverride = null; },
    },
    __chat: {
      enable: () => useStore.setState({ chatAvailable: true }),
      mock: (responseJson: string) => {
        chatLlmOverride = { isAvailable: () => true, complete: async () => responseJson };
      },
      // Streaming seam (E4): emits the response in `chunks` deltas, then resolves
      // with the full text — mirrors the real completeStream contract.
      mockStream: (responseJson: string, chunks = 3) => {
        chatLlmOverride = {
          isAvailable: () => true,
          complete: async () => responseJson,
          completeStream: async (_req, onDelta) => {
            const size = Math.max(1, Math.ceil(responseJson.length / chunks));
            for (let i = 0; i < responseJson.length; i += size) onDelta(responseJson.slice(i, i + size));
            return responseJson;
          },
        };
      },
      reset: () => { chatLlmOverride = null; mcpToolsCache = null; },
      setMcpCache: (endpoint: string, tools: import("../ports/McpPort").McpTool[]) => {
        mcpToolsCache = { endpoint, tools };
      },
    },
  };
}
