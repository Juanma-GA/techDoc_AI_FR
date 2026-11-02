import { Alert, Card, CardContent, CardHeader, CardTitle, PageHeader } from "@internal/ui";
import { useTranslation } from "react-i18next";

export function Architecture() {
  const { t } = useTranslation();
  const workflow = Array.from({ length: 6 }, (_, index) =>
    t(`architecture.workflow.${index}`),
  );
  const pipeline = Array.from({ length: 6 }, (_, index) =>
    t(`architecture.pipeline.${index}`),
  );

  return (
    <div className="space-y-4">
      <PageHeader title={t("architecture.title")} description={t("architecture.subtitle")} />

      <Card>
        <CardHeader><CardTitle>{t("architecture.layersTitle")}</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-md bg-bg-2 p-4">
            <div className="text-label font-mono uppercase text-brand-text">
              {t("architecture.documentChangeTitle")}
            </div>
            <p className="mt-2">{t("architecture.documentChangeText")}</p>
          </div>
          <div className="rounded-lg border border-md bg-bg-2 p-4">
            <div className="text-label font-mono uppercase text-info">
              {t("architecture.projectChangeTitle")}
            </div>
            <p className="mt-2">{t("architecture.projectChangeText")}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("architecture.workflowTitle")}</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-fg-dim">{t("architecture.workflowIntro")}</p>
          <div className="mt-2 flex flex-col gap-1.5">
            {workflow.map((step, index) => (
              <div key={index} className="flex items-start gap-2.5 rounded-sm border-l border-brand bg-bg-2 px-3 py-2 text-sm">
                <span className="font-mono text-brand-text">{index}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("architecture.pipelineTitle")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-col gap-1.5">
            {pipeline.map((step, index) => (
              <div key={index} className="flex items-start gap-2.5 rounded-sm border-l border-brand bg-bg-2 px-3 py-2 text-sm">
                <span className="font-mono text-brand-text">{String.fromCharCode(65 + index)}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
          <Alert className="mt-3" variant="warning">
            {t("architecture.outputWarning")}
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}
