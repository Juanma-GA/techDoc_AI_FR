import { Badge, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

type Health = { status: string; version: string; db: string; llm: string };

export function Home() {
  const { t } = useTranslation();
  const health = useQuery<Health>({
    queryKey: ["health"],
    queryFn: async () => {
      const r = await fetch("/api/v1/health");
      return (await r.json()) as Health;
    },
  });

  const steps = [t("home.step1"), t("home.step2"), t("home.step3"), t("home.step4")];

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("home.title")}</h1>
        <p className="text-fg-dim">{t("home.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("home.workflowTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="flex flex-col gap-2">
            {steps.map((s, i) => (
              <li
                key={i}
                className="flex gap-3 rounded-sm border-l-2 border-brand-blue bg-bg-2 px-3 py-2 text-sm"
              >
                <span className="font-mono font-bold text-brand-blue-light">{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
          <div className="mt-4 flex items-center gap-2 text-sm text-fg-dim">
            <span>{t("home.backendStatus")} :</span>
            {health.data ? (
              <>
                <Badge variant="success">{health.data.status}</Badge>
                <span>LLM :</span>
                <Badge variant={health.data.llm === "ok" ? "success" : "warning"}>
                  {health.data.llm}
                </Badge>
                <span className="font-mono text-label">v{health.data.version}</span>
              </>
            ) : (
              <Badge variant="warning">?</Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
