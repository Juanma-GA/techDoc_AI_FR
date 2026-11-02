import { useQuery } from "@tanstack/react-query";
import { Alert, Badge, Card, CardContent, CardHeader, CardTitle, PageHeader } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { healthApi, type HealthDto } from "../lib/api";

export function Home() {
  const { t } = useTranslation();
  const { data: health } = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
  });

  return (
    <div className="space-y-4">
      <PageHeader title={t("home.title")} description={t("home.subtitle")} />
      <Card>
        <CardHeader><CardTitle>{t("home.cardTitle")}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p>{t("home.description")}</p>
          <p>{t("home.principle")}</p>
          <Alert variant="warning" title={t("home.bestEffortTitle")}>
            {t("home.bestEffort")}
          </Alert>
          <Alert variant="info" icon={null}>
            <span>{t("home.backendStatus")} </span>
            <Badge variant={health ? "success" : "warning"}>
              {health ? health.status : t("home.unknown")}
            </Badge>
            {health ? (
              <span className="ml-2">
                {t("home.version")} <code>{health.version}</code>
              </span>
            ) : null}
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}
