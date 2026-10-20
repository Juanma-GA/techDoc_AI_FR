import { useTranslation } from "react-i18next";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DemoScenarioPanel,
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
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>{t("home.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-fg-dim">{t("home.subtitle")}</p>
      </CardContent>
    </Card>
  );
}
