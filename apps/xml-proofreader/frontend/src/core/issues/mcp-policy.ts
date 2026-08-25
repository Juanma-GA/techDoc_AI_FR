// MCP read-only guardrails (D9 / ADR-0019).
//
// DocReview is a *review* tool: the original XML is the source of truth and all
// annotations are applied by non-destructive source-splicing (ADR-0003, CLAUDE.md
// §7). The MCP server (Oxygen) must therefore NEVER edit or write files on our
// behalf. This module is a defensive client-side barrier that decides which MCP
// tools may be advertised to the model and executed.
//
// Policy: **default-deny allowlist.** A tool is allowed only if its name matches a
// read-only/consultative verb AND does not match any mutating verb. Anything we
// don't recognise as read-only is blocked. This is a heuristic safety net, not a
// guarantee — the real guarantee is that we only pass in-memory content to tools
// (never file paths), so a tool cannot locate the user's file to corrupt it.

// We match per *token* (a tool name is split on camelCase and on non-alphanumeric
// separators like "_", "-", "."), so "read_metadata" yields ["read","metadata"].
// This avoids the `\b`-vs-underscore pitfall (in JS `_` is a word char, so
// /\bread\b/ would NOT match "read_metadata"). A token matches a stem when it
// starts with that stem ("validate" ⊃ "validat", "checks" ⊃ "check").

/** Stems that indicate a read-only / consultative operation (validation, query). */
const READ_ONLY_STEMS = [
  "validat", "verif", "check", "lint", "diagnos",
  "quer", "search", "find", "get", "list", "read",
  "inspect", "analy", "report", "describe", "schema", "preview",
];

/** Stems that indicate a mutating operation (edit, write, delete, …). A match
 *  here blocks the tool even if it also looks read-only ("validate_and_save"). */
const MUTATING_STEMS = [
  "writ", "edit", "modif", "updat", "delet", "remov", "creat",
  "insert", "replac", "refactor", "format", "save", "renam",
  "apply", "set", "move", "transform", "generat", "commit", "fix",
];

function tokenize(name: string): string[] {
  return name
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2") // split camelCase
    .split(/[^A-Za-z0-9]+/)                  // split on _ - . space etc.
    .filter(Boolean)
    .map((s) => s.toLowerCase());
}

function anyToken(tokens: string[], stems: string[]): boolean {
  return tokens.some((t) => stems.some((s) => t.startsWith(s)));
}

/** True iff the tool may be advertised and executed (read-only, non-mutating). */
export function isToolAllowed(name: string): boolean {
  if (!name) return false;
  const tokens = tokenize(name);
  if (anyToken(tokens, MUTATING_STEMS)) return false; // mutating wins
  return anyToken(tokens, READ_ONLY_STEMS);
}

/** Keep only the tools allowed by the read-only policy. */
export function filterAllowedTools<T extends { name: string }>(tools: T[]): T[] {
  return tools.filter((t) => isToolAllowed(t.name));
}

/** Human-readable reason a tool is blocked (for toasts / tooltips). */
export function toolBlockedReason(name: string): string {
  return `Tool "${name}" is blocked by the read-only MCP policy (DocReview never lets MCP edit files).`;
}
