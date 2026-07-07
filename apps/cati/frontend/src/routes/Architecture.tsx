import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@internal/ui";

const STACK: Array<[string, string]> = [
  ["Backend", "FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog"],
  ["Extraction PDF", "PyMuPDF (find_tables) — regroupement Client/Interne/Fournisseur"],
  ["Ecriture Excel", "openpyxl — template Catalogue fixe, styles & feuille Suivi preserves"],
  ["LLM", "Mistral via httpx (filet optionnel, desactivable)"],
  ["Frontend", "React 18 + TS + Vite + Tailwind + TanStack Query + i18next + Zustand"],
];

export function Architecture() {
  const { t } = useTranslation();
  const steps = t("architecture.steps", { returnObjects: true }) as string[];

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("architecture.pipelineTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-fg-dim">
            {Array.isArray(steps) && steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("architecture.stackTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2 text-sm">
            {STACK.map(([k, v]) => (
              <div key={k} className="flex flex-col gap-0.5">
                <dt className="label">{k}</dt>
                <dd className="text-fg-dim">{v}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
