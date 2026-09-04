import { useStore } from "../../store";
import { buildPiGroups, buildThreadPiGroups } from "../../../core/oxygen/serialize";
import { toOxygenTime } from "../../../core/oxygen/time";

export function XmlSourceTab() {
  const activeId = useStore((s) => s.activeId);
  const comments = useStore((s) => s.comments);
  const c = comments.find((x) => x.id === activeId);

  let fragment = "Select a comment to see its XML source.";
  if (c) {
    if (c.replies && c.replies.length > 0) {
      const { open, close } = buildThreadPiGroups({
        root: { author: c.author, timestamp: c.timestamp, text: c.text, color: c.color, resolved: c.resolved, id: c.id },
        replies: c.replies.map((r, i) => ({
          author: r.author, timestamp: r.timestamp, text: r.text, parentId: c.id, mid: i + 1, resolved: r.resolved,
        })),
      });
      fragment = `…${open}${c.anchor.quote}${close}…`;
    } else {
      const { open, close } = buildPiGroups({
        author: c.author, timestamp: c.timestamp, text: c.text, color: c.color,
        resolved: c.resolved, forceComment: c.text.trim() === "" && c.id.startsWith("c:"),
      });
      fragment = `…${open}${c.anchor.quote}${close}…`;
      if (c.text) fragment = fragment.replace(/timestamp="[^"]+"/, `timestamp="${toOxygenTime(c.timestamp)}"`);
    }
  }
  return (
    <div className="rp-body rp-xml">
      <pre style={{ margin: 0, padding: 14, background: "var(--code-bg)", color: "var(--code-fg)", fontFamily: "var(--mono)", fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word", height: "100%" }}>
        {fragment}
      </pre>
    </div>
  );
}
