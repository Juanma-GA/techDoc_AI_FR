import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { buttonVariants, Card, CardContent, CardHeader, CardTitle } from "@internal/ui";

export function Home() {
  const { t } = useTranslation();
  const steps = t("home.steps", { returnObjects: true }) as string[];

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("home.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-fg-dim">{t("home.subtitle")}</p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-fg-dim">
            {Array.isArray(steps) && steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <Link to="/import" className={buttonVariants({ variant: "primary" })}>
            {t("home.cta")}
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
