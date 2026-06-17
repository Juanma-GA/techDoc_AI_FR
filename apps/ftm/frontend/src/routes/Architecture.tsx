/**
 * Vue Architecture — présentation synthétique de la stack technique et du
 * workflow utilisateur en 6 étapes. Contenu statique, i18n FR/EN.
 * HTML inline via dangerouslySetInnerHTML : contenu issu du bundle backend
 * contrôlé, jamais de l'input utilisateur.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";

const WORKFLOW_STEPS = ["f1", "f2", "f3", "f4", "f5", "f6"] as const;

export function Architecture() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 p-6">
      <PageHeader title={t("nav.architecture")} subtitle={t("page.architecture")} />

      {/* Card 1 — split Backend / Frontend */}
      <Card>
        <CardHeader>
          <CardTitle>{t("arch.split.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <p className="label mb-2 uppercase tracking-wide text-fg-dim">Backend</p>
              <p
                className="text-sm leading-relaxed [&_code]:rounded [&_code]:bg-card-hover [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs"
                dangerouslySetInnerHTML={{ __html: t("arch.split.back") }}
              />
            </div>
            <div>
              <p className="label mb-2 uppercase tracking-wide text-fg-dim">Frontend</p>
              <p
                className="text-sm leading-relaxed [&_code]:rounded [&_code]:bg-card-hover [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs"
                dangerouslySetInnerHTML={{ __html: t("arch.split.front") }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Card 2 — workflow 6 étapes numérotées */}
      <Card>
        <CardHeader>
          <CardTitle>{t("arch.flowTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4">
            {WORKFLOW_STEPS.map((key, idx) => (
              <li key={key} className="flex gap-3 text-sm">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-fg">
                  {idx + 1}
                </span>
                <span
                  className="leading-relaxed [&_code]:rounded [&_code]:bg-card-hover [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs"
                  dangerouslySetInnerHTML={{ __html: t(`arch.${key}`) }}
                />
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
