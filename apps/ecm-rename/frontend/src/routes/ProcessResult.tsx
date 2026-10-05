import { useTranslation } from "react-i18next";

import type { ProcessDto } from "../lib/api";

export function ProcessResult({ result }: { result: ProcessDto }) {
  const { t } = useTranslation();

  return (
    <section aria-label={t("home.result_title")} className="mt-4 border-t border-md pt-4">
      <h2 className="font-display text-lg text-fg">{t("home.result_title")}</h2>
      <p className="mt-1 text-sm text-success" role="status">
        {t("home.process_success", { count: result.rows_written })}
      </p>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="label">{t("home.tracker_updated")}</dt>
          <dd className="mt-1 break-all font-mono text-sm text-fg">{result.tracker_path}</dd>
        </div>
      </dl>
      <h3 className="label mt-4">{t("home.created_folders")}</h3>
      <ul className="mt-2 flex flex-col gap-2">
        {result.created_folders.map((folder) => (
          <li key={folder} className="break-all border-l-2 border-brand-blue-light pl-3 font-mono text-sm">
            {folder}
          </li>
        ))}
      </ul>
    </section>
  );
}