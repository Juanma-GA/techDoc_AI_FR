import { useTranslation } from "react-i18next";
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DemoScenarioPanel,
  PageHeader,
  useDemoMode,
  type DemoScenario,
} from "@internal/ui";

export function Home() {
  const { t } = useTranslation();

  const { mode, isReady } = useDemoMode();
  if (isReady && mode === "demo") {
    const scenario: DemoScenario = {
      id: "text-summary",
      title: t("demo.scenarioTitle"),
      description: t("demo.scenarioDescription"),
      inputs: [
        {
          id: "text",
          label: t("demo.textLabel"),
          initialValue: t("demo.sampleText"),
          multiline: true,
        },
      ],
      files: [
        {
          id: "sample-text",
          name: t("demo.sampleFileName"),
          mediaType: "text/plain",
          content: t("demo.sampleFileContent"),
        },
      ],
      run: ({ inputs, files }) => {
        const text = (inputs.text ?? "").trim();
        const wordCount = text ? text.split(/\s+/).length : 0;
        const fileCharacters = files.reduce(
          (count, file) => count + (typeof file.content === "string" ? file.content.length : 0),
          0,
        );
        return [
          `${t("demo.outputWords")}: ${wordCount}`,
          `${t("demo.outputCharacters")}: ${text.length}`,
          `${t("demo.outputFileCharacters")}: ${fileCharacters}`,
        ].join("\n");
      },
    };

    return (
      <DemoScenarioPanel
        scenarios={[scenario]}
        labels={{
          title: t("demo.panelTitle"),
          description: t("demo.panelDescription"),
          scenario: t("demo.scenarioLabel"),
          sampleFiles: t("demo.sampleFiles"),
          run: t("demo.run"),
          reset: t("demo.reset"),
          result: t("demo.result"),
          empty: t("demo.empty"),
          error: t("demo.error"),
        }}
      />
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PageHeader title={t("home.title")} description={t("home.subtitle")} />
      <Card>
        <CardHeader>
          <CardTitle>{t("home.nextSteps")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="m-0 flex list-decimal flex-col gap-2 pl-5 text-fg-dim">
            <li>{t("home.stepRoutes")}</li>
            <li>{t("home.stepApi")}</li>
            <li>{t("home.stepLocales")}</li>
          </ol>
        </CardContent>
      </Card>
      {import.meta.env.DEV ? <Alert variant="info">{t("home.designHint")}</Alert> : null}
    </div>
  );
}
