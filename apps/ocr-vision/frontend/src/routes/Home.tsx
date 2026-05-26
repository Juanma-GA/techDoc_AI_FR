import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@internal/ui";

export function Home() {
  const { t } = useTranslation();
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
