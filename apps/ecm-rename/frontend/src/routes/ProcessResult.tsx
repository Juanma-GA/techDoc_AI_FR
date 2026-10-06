import { useTranslation } from "react-i18next";

import type { AppendTrackerDto, CreateFoldersDto } from "../lib/api";

type ProcessResultProps = {
  folderResult: CreateFoldersDto | null;
  trackerResult: AppendTrackerDto | null;
};

export function ProcessResult({ folderResult, trackerResult }: ProcessResultProps) {
  const { t } = useTranslation();

  return (
    <section aria-label={t("home.result_title")} className="mt-4 border-t border-md pt-4">
      <h2 className="font-display text-lg text-fg">{t("home.result_title")}</h2>
      {folderResult && (
        <div className="mt-3">
          <p className="text-sm text-success" role="status">
            {t("home.folders_success", { count: folderResult.created_folders.length })}
          </p>
          <h3 className="label mt-3">{t("home.created_folders")}</h3>
          <ul className="mt-2 flex flex-col gap-2">
            {folderResult.created_folders.map((folder) => (
              <li key={folder} className="break-all border-l-2 border-brand-blue-light pl-3 font-mono text-sm">
                {folder}
              </li>
            ))}
          </ul>
        </div>
      )}
      {trackerResult && (
        <div className="mt-4 border-t border-md pt-3">
          <p className="text-sm text-success" role="status">
            {t("home.tracker_success", { count: trackerResult.rows_written })}
          </p>
          <dl className="mt-3">
            <div className="min-w-0">
              <dt className="label">{t("home.tracker_updated")}</dt>
              <dd className="mt-1 break-all font-mono text-sm text-fg">{trackerResult.tracker_path}</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}