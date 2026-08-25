import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CommentsTab } from "../../src/ui/comments/tabs/CommentsTab";
import { useStore } from "../../src/ui/store";
import { useSession } from "../../src/ui/sessionStore";
import type { ParsedComment } from "../../src/core/oxygen/parse";
import type { Comment } from "../../src/core/model/types";
import { defaultSettings } from "../../src/core/workspace/types";

function makeReply(): Comment {
  return {
    id: "r:1", author: "Bob", timestamp: Date.now(), text: "a reply",
    color: "yellow", resolved: false, parentId: "c:1",
    anchor: { nodePath: [0], startOffset: 0, endOffset: 0, quote: "" },
  };
}

function makeRoot(replies: Comment[]): ParsedComment {
  return {
    id: "c:1", author: "Alice", timestamp: Date.now(), text: "root comment",
    color: "green", resolved: false,
    anchor: { nodePath: [0], startOffset: 0, endOffset: 5, quote: "hello" },
    replies,
    key: 0,
    spans: { openStart: 0, contentStart: 10, contentEnd: 20, closeEnd: 30 },
  };
}

function makeResolved(): ParsedComment {
  return {
    id: "c:resolved", author: "Alice", timestamp: Date.now(), text: "resolved comment",
    color: "yellow", resolved: true,
    anchor: { nodePath: [0], startOffset: 0, endOffset: 5, quote: "hello" },
    replies: [],
    key: 1,
    spans: { openStart: 0, contentStart: 10, contentEnd: 20, closeEnd: 30 },
  };
}

// F2 (ADR-0025): showResolved is now in sessionStore.prefs — CommentsTab must read it there.
describe("CommentsTab — F2: showResolved controlled by sessionStore.prefs", () => {
  beforeEach(() => {
    useStore.setState({
      filter: "all", search: "",
      activeId: null, editingId: null, editingText: "", history: {},
      setColor: vi.fn(),
    });
    // Reset to default settings (showResolved: true by default).
    useSession.setState({ settings: defaultSettings() });
  });

  it("hides resolved comments when prefs.showResolved is false", () => {
    const prefs = { ...defaultSettings().prefs, showResolved: false };
    useSession.setState({ settings: { ...defaultSettings(), prefs } });
    useStore.setState({ comments: [makeRoot([]), makeResolved()] });
    render(<CommentsTab />);

    // The open comment (makeRoot) should be visible.
    expect(screen.getByText("root comment")).toBeInTheDocument();
    // The resolved comment must be filtered out.
    expect(screen.queryByText("resolved comment")).toBeNull();
  });

  it("shows resolved comments when prefs.showResolved is true", () => {
    const prefs = { ...defaultSettings().prefs, showResolved: true };
    useSession.setState({ settings: { ...defaultSettings(), prefs } });
    useStore.setState({ comments: [makeRoot([]), makeResolved()] });
    render(<CommentsTab />);

    expect(screen.getByText("root comment")).toBeInTheDocument();
    expect(screen.getByText("resolved comment")).toBeInTheDocument();
  });
});

describe("CommentsTab — D1: root keeps its color with replies", () => {
  let setColor: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    setColor = vi.fn();
    useStore.setState({
      filter: "all", search: "",
      activeId: null, editingId: null, editingText: "", history: {},
      setColor,
    });
  });

  it("shows the swatch and Color dropdown on a root that has replies", () => {
    useStore.setState({ comments: [makeRoot([makeReply()])] });
    const { container } = render(<CommentsTab />);

    // Swatch in the root card header is present even with replies.
    expect(container.querySelector(".cnode.is-root .swatch-sm")).not.toBeNull();
    // The "Color ▾" dropdown button is available.
    expect(screen.getByRole("button", { name: /color/i })).toBeInTheDocument();
  });

  it("still shows the swatch and Color dropdown on a root without replies", () => {
    useStore.setState({ comments: [makeRoot([])] });
    const { container } = render(<CommentsTab />);

    expect(container.querySelector(".cnode.is-root .swatch-sm")).not.toBeNull();
    expect(screen.getByRole("button", { name: /color/i })).toBeInTheDocument();
  });

  it("wires the color menu to setColor(rootId, color) on a thread with replies", () => {
    useStore.setState({ comments: [makeRoot([makeReply()])] });
    const { container } = render(<CommentsTab />);

    fireEvent.click(screen.getByRole("button", { name: /color/i }));
    const firstSwatch = container.querySelector(".cmenu .swatch-sm");
    expect(firstSwatch).not.toBeNull();
    fireEvent.click(firstSwatch!);

    // COLORS[0] === "yellow"; the click must target the root comment id.
    expect(setColor).toHaveBeenCalledWith("c:1", "yellow");
  });
});
