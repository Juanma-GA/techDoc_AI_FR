import { Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useTranslation } from "react-i18next";

import type { ProcessDto } from "../lib/api";

export function Data({ result }: { result: ProcessDto | null }) {
  const { t } = useTranslation();

  return (
    <section className="max-w-4xl">
      <header className="page-header">
        <div>
          <h1>{t("data.title")}</h1>
          <p>{t("data.subtitle")}</p>
        </div>
      </header>
      {!result ? (
        <p className="text-sm text-fg-dim">{t("data.empty")}</p>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{t("data.rows", { count: result.rows_written })}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div>
              <h2 className="label">{t("data.tracker")}</h2>
              <p className="break-all font-mono text-sm">{result.tracker_path}</p>
            </div>
            <div>
              <h2 className="label">{t("data.backup")}</h2>
              <p className="break-all font-mono text-sm">{result.backup_path}</p>
            </div>
            <div>
              <h2 className="label">{t("data.folders")}</h2>
              <ul className="mt-2 flex flex-col gap-2">
                {result.created_folders.map((folder) => (
                  <li key={folder} className="break-all border-l-2 border-brand-blue-light pl-3 font-mono text-sm">
                    {folder}
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  );
}