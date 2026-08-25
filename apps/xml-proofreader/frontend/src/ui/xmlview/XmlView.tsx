// Read-only XML source view (CodeMirror 6). Shows the authoritative buffer,
// including the Oxygen review PIs, with XML syntax highlighting.
import CodeMirror from "@uiw/react-codemirror";
import { xml } from "@codemirror/lang-xml";
import { EditorView } from "@codemirror/view";
import { useStore } from "../store";

const readOnlyTheme = EditorView.theme({
  "&": { backgroundColor: "var(--code-bg)", color: "var(--code-fg)", fontSize: "12px" },
  ".cm-gutters": { backgroundColor: "var(--code-bg)", color: "var(--code-gutter)", border: "none" },
  ".cm-activeLine": { backgroundColor: "transparent" },
  ".cm-activeLineGutter": { backgroundColor: "transparent" },
  ".cm-content": { fontFamily: "var(--mono)" },
});

export function XmlView() {
  const buffer = useStore((s) => s.buffer);
  return (
    <div className="cm-theme">
      <CodeMirror
        value={buffer}
        editable={false}
        readOnly
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: false }}
        extensions={[xml(), readOnlyTheme, EditorView.lineWrapping]}
        theme="dark"
      />
    </div>
  );
}
