import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { CheckCircle2, Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";

import { AssistantPanel } from "../components/editor/AssistantPanel";
import { ExportBar } from "../components/editor/ExportBar";
import { NodeTable } from "../components/editor/NodeTable";
import { PreviewPanel } from "../components/editor/PreviewPanel";
import { SavePanel } from "../components/editor/SavePanel";
import { useEditorStore } from "../stores/editorStore";

// Deux colonnes : assistant (gauche) | logigramme (droite), chacune defile independamment.
export function Editor() {
  const { t } = useTranslation();
  const { graph, warnings, llmUsed, currentFlowId, clear, validated, setValidated } = useEditorStore();

  return (
    <div className="flex flex-col gap-4 lg:h-full lg:min-h-0">
      <div className="page-header">
        <h1>{t("editor.title")}</h1>
        <div className="page-header-actions">
          <Button variant="ghost" size="sm" onClick={clear}>
            {currentFlowId ? t("editor.newFlow") : t("editor.reset")}
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card className="flex flex-col lg:min-h-0" data-testid="assistant-column">
          <CardHeader>
            <CardTitle>{t("editor.assistant.title")}</CardTitle>
          </CardHeader>
          <CardContent className="flex min-h-[32rem] flex-1 flex-col lg:min-h-0">
            <AssistantPanel />
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4 lg:min-h-0 lg:overflow-y-auto lg:pr-1" data-testid="diagram-column">
          <Card className="shrink-0">
            <CardHeader>
              <CardTitle>{graph ? graph.title : t("editor.preview.title")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {graph && (
                <div className="flex flex-wrap items-center gap-2 text-fg-dim">
                  {graph.system && <Badge>{graph.system}</Badge>}
                  {graph.fault_code && <Badge variant="info">{graph.fault_code}</Badge>}
                  <span>{t("editor.counts", { nodes: graph.nodes.length, edges: graph.edges.length })}</span>
                  {llmUsed && <Badge variant="success">{t("editor.llmUsed")}</Badge>}
                </div>
              )}
              {warnings.length > 0 && (
                <ul className="list-disc pl-5 text-warning" data-testid="parse-warnings">
                  {warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
              <PreviewPanel graph={graph} />
              {graph && !validated && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded border p-3">
                  <span className="text-fg-dim">{t("editor.validateHelp")}</span>
                  <Button onClick={() => setValidated(true)} data-testid="validate-flow">
                    <CheckCircle2 size={14} aria-hidden /> {t("editor.validate")}
                  </Button>
                </div>
              )}
              {graph && validated && (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant="success">{t("editor.validated")}</Badge>
                    <Button variant="ghost" size="sm" onClick={() => setValidated(false)}>
                      <Pencil size={14} aria-hidden /> {t("editor.modify")}
                    </Button>
                  </div>
                  <ExportBar graph={graph} />
                </>
              )}
            </CardContent>
          </Card>

          {graph && (
            <>
              <Card className="shrink-0">
                <CardHeader>
                  <CardTitle>{t("editor.save.title")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <SavePanel graph={graph} />
                </CardContent>
              </Card>
              <Card className="shrink-0">
                <CardHeader>
                  <CardTitle>{t("editor.nodes.title")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <NodeTable graph={graph} />
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
