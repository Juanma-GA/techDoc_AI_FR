// ============================================================
// Lossless positional XML scanner.
//
// Produces a PosNode tree where every node carries exact byte offsets into
// the original buffer. The invariant (verified by tests) is *perfect tiling*:
// concatenating the source spans of the tree reproduces the input byte for
// byte. Nothing is normalized — entities, whitespace, attribute quoting,
// comments, processing instructions and the DOCTYPE internal subset are all
// preserved verbatim. This is the foundation of non-destructive editing:
// annotations are spliced into this buffer at offsets, never reserialized.
//
// Non-validating by design. It accepts well-formed XML and is tolerant of the
// document-type variety found across DITA 1.3 specializations.
// ============================================================

import type { PosNode } from "../model/types";

const NAME_STOP = /[\s/>]/;
const ATTR_NAME_STOP = /[\s=/>]/;

export class XmlParseError extends Error {
  constructor(message: string, public offset: number) {
    super(`${message} (at offset ${offset})`);
    this.name = "XmlParseError";
  }
}

export function parseXml(buffer: string): PosNode {
  const doc: PosNode = {
    kind: "document",
    start: 0,
    end: buffer.length,
    children: [],
  };
  const stack: PosNode[] = [doc];
  let i = 0;
  const n = buffer.length;

  const top = () => stack[stack.length - 1];
  const push = (node: PosNode) => {
    node.parent = top();
    top().children!.push(node);
  };

  while (i < n) {
    if (buffer[i] === "<") {
      const c1 = buffer[i + 1];
      if (c1 === "?") {
        i = scanPI(buffer, i, push);
      } else if (c1 === "!") {
        if (buffer.startsWith("<!--", i)) {
          i = scanComment(buffer, i, push);
        } else if (buffer.startsWith("<![CDATA[", i)) {
          i = scanCData(buffer, i, push);
        } else {
          i = scanMarkupDecl(buffer, i, push); // DOCTYPE / other <! declarations
        }
      } else if (c1 === "/") {
        i = scanEndTag(buffer, i, stack);
      } else {
        i = scanStartTag(buffer, i, push, stack);
      }
    } else {
      i = scanText(buffer, i, push);
    }
  }

  if (stack.length !== 1) {
    const unclosed = top();
    throw new XmlParseError(`Unclosed element <${unclosed.name}>`, unclosed.start);
  }
  return doc;
}

function scanText(buffer: string, start: number, push: (n: PosNode) => void): number {
  let i = start;
  while (i < buffer.length && buffer[i] !== "<") i++;
  push({
    kind: "text",
    start,
    end: i,
    value: buffer.slice(start, i),
  });
  return i;
}

function scanPI(buffer: string, start: number, push: (n: PosNode) => void): number {
  const close = buffer.indexOf("?>", start + 2);
  const end = close === -1 ? buffer.length : close + 2;
  // PI target = chars after "<?" up to whitespace or "?>"
  let j = start + 2;
  while (j < end && !/\s/.test(buffer[j]) && !buffer.startsWith("?>", j)) j++;
  const name = buffer.slice(start + 2, j);
  push({
    kind: name.toLowerCase() === "xml" ? "doctype" : "pi",
    name,
    start,
    end,
    value: buffer.slice(start, end),
  });
  return end;
}

function scanComment(buffer: string, start: number, push: (n: PosNode) => void): number {
  const close = buffer.indexOf("-->", start + 4);
  const end = close === -1 ? buffer.length : close + 3;
  push({ kind: "comment", start, end, value: buffer.slice(start, end) });
  return end;
}

function scanCData(buffer: string, start: number, push: (n: PosNode) => void): number {
  const close = buffer.indexOf("]]>", start + 9);
  const end = close === -1 ? buffer.length : close + 3;
  push({ kind: "cdata", start, end, value: buffer.slice(start, end) });
  return end;
}

// DOCTYPE (and any "<!...>" declaration). Handles an internal subset
// "[ ... ]" that may itself contain ">" inside quotes or nested declarations.
function scanMarkupDecl(buffer: string, start: number, push: (n: PosNode) => void): number {
  let i = start + 2;
  let depth = 0;
  let quote: string | null = null;
  while (i < buffer.length) {
    const ch = buffer[i];
    if (quote) {
      if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === "[") {
      depth++;
    } else if (ch === "]") {
      if (depth > 0) depth--;
    } else if (ch === ">" && depth === 0) {
      i++;
      break;
    }
    i++;
  }
  push({ kind: "doctype", start, end: i, value: buffer.slice(start, i) });
  return i;
}

function scanEndTag(buffer: string, start: number, stack: PosNode[]): number {
  let j = start + 2;
  while (j < buffer.length && !NAME_STOP.test(buffer[j])) j++;
  const name = buffer.slice(start + 2, j);
  const gt = buffer.indexOf(">", j);
  const end = gt === -1 ? buffer.length : gt + 1;

  // Pop the matching open element; record its inner/outer bounds.
  for (let s = stack.length - 1; s >= 1; s--) {
    if (stack[s].name === name) {
      const el = stack[s];
      el.innerEnd = start;
      el.end = end;
      stack.length = s; // pop el and anything left open inside it
      return end;
    }
  }
  throw new XmlParseError(`Unexpected end tag </${name}>`, start);
}

function scanStartTag(
  buffer: string,
  start: number,
  push: (n: PosNode) => void,
  stack: PosNode[]
): number {
  let j = start + 1;
  while (j < buffer.length && !NAME_STOP.test(buffer[j])) j++;
  const name = buffer.slice(start + 1, j);

  const { attrs, end, selfClose } = scanAttributes(buffer, j);

  const node: PosNode = {
    kind: "element",
    name,
    attrs,
    classAttr: attrs["class"],
    start,
    end, // provisional; overwritten on close for container elements
    innerStart: end,
  };
  push(node);

  if (selfClose) {
    node.innerEnd = end;
    node.children = node.children ?? [];
  } else {
    node.children = [];
    stack.push(node);
  }
  return end;
}

function scanAttributes(
  buffer: string,
  from: number
): { attrs: Record<string, string>; end: number; selfClose: boolean } {
  const attrs: Record<string, string> = {};
  let i = from;
  const n = buffer.length;
  while (i < n) {
    while (i < n && /\s/.test(buffer[i])) i++;
    if (i >= n) break;
    if (buffer[i] === ">") return { attrs, end: i + 1, selfClose: false };
    if (buffer[i] === "/" && buffer[i + 1] === ">") return { attrs, end: i + 2, selfClose: true };

    // attribute name
    const ns = i;
    while (i < n && !ATTR_NAME_STOP.test(buffer[i])) i++;
    const aname = buffer.slice(ns, i);
    while (i < n && /\s/.test(buffer[i])) i++;
    if (buffer[i] === "=") {
      i++;
      while (i < n && /\s/.test(buffer[i])) i++;
      const q = buffer[i];
      if (q === '"' || q === "'") {
        const vstart = i + 1;
        const vend = buffer.indexOf(q, vstart);
        const realEnd = vend === -1 ? n : vend;
        attrs[aname] = buffer.slice(vstart, realEnd);
        i = realEnd + 1;
      } else {
        // unquoted value (rare/non-spec) — read until whitespace or tag end
        const vstart = i;
        while (i < n && !/[\s/>]/.test(buffer[i])) i++;
        attrs[aname] = buffer.slice(vstart, i);
      }
    } else if (aname) {
      attrs[aname] = ""; // valueless attribute
    }
  }
  return { attrs, end: n, selfClose: false };
}
