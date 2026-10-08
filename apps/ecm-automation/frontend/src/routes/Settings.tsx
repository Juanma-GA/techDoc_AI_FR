import { useTranslation } from "react-i18next";

export function Settings() {
  const { t } = useTranslation();

  return (
    <div className="max-w-xl">
      <header className="page-header">
        <div>
          <h1>{t("settings.title")}</h1>
        </div>
      </header>
    </div>
  );
}
