import { Badge, Button, Spinner } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { FileText, Paperclip, X } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { errorText } from "../../lib/api";
import { assistantApi } from "../../lib/flowApi";
import { useEditorStore } from "../../stores/editorStore";
import type { AttachResult, SourceType } from "../../types/flow";

export const ACCEPTED_FILES = ".xlsx,.xlsm,.csv,.json,.dsl,.flow,.txt,.md,.docx,.pdf,.pptx";

const sourceTypeOf = (name: string): SourceType => {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  if (["xlsx", "xlsm", "csv"].includes(ext)) return "table";
  return ext === "json" ? "json" : "dsl";
};

// Import d'un fichier joint : graphe direct (Excel, CSV, JSON, DSL) ou document de reference.
export function useAttachFile(onError: (message: string | null) => void) {
  const { t } = useTranslation();
  const { applyParse, pushMessage, addDocument } = useEditorStore();

  const mutation = useMutation({
    mutationFn: (file: File) => assistantApi.attach(file),
    onMutate: () => onError(null),
    onSuccess: (res: AttachResult) => {
      if (res.kind === "graph" && res.graph) {
        applyParse({ graph: res.graph, warnings: res.warnings, llm_used: false }, sourceTypeOf(res.name), res.name);
        const nodes = res.graph.nodes.length;
        pushMessage({ role: "assistant", content: t("editor.assistant.imported", { name: res.name, nodes }) });
        return;
      }
      addDocument({ name: res.name, text: res.text });
      const key = res.truncated ? "editor.assistant.documentTruncated" : "editor.assistant.documentAdded";
      pushMessage({ role: "assistant", content: t(key, { name: res.name }) });
    },
    onError: (e: unknown) => onError(errorText(e)),
  });

  const attachFiles = (files: FileList | File[] | null): Promise<void> =>
    Promise.allSettled(Array.from(files ?? []).map((file) => mutation.mutateAsync(file))).then(() => undefined);

  return { attachFiles, isPending: mutation.isPending };
}

type AttachButtonProps = { disabled: boolean; pending: boolean; onFiles: (files: FileList | null) => void };

export function AttachButton({ disabled, pending, onFiles }: AttachButtonProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_FILES}
        className="hidden"
        data-testid="assistant-file-input"
        onChange={(e) => {
          onFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <Button
        variant="ghost"
        size="sm"
        disabled={disabled || pending}
        title={t("editor.assistant.attachHelp")}
        onClick={() => inputRef.current?.click()}
      >
        {pending ? <Spinner size="sm" /> : <Paperclip size={14} aria-hidden />} {t("editor.assistant.attach")}
      </Button>
    </>
  );
}

export function DocumentChips() {
  const { t } = useTranslation();
  const { documents, removeDocument } = useEditorStore();
  if (documents.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2" data-testid="assistant-documents">
      {documents.map((d) => (
        <Badge key={d.name} variant="info" className="normal-case">
          <FileText size={12} aria-hidden />
          <span className="max-w-[12rem] truncate">{d.name}</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-5 w-5 p-0"
            aria-label={t("editor.assistant.removeDocument", { name: d.name })}
            title={t("editor.assistant.removeDocument", { name: d.name })}
            onClick={() => removeDocument(d.name)}
          >
            <X size={12} aria-hidden />
          </Button>
        </Badge>
      ))}
    </div>
  );
}
