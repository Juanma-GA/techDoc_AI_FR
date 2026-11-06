import { Badge, Button, Spinner } from "@internal/ui";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { CatpartCompareDto } from "../../lib/catpartApi";

const GROUP_PAGE_SIZE = 100;
const FILE_PREVIEW_SIZE = 10;

type Props = {
  result: CatpartCompareDto;
  isExporting: boolean;
  exportError: string | null;
  onExportExcel: () => void;
};

function FileList({ label, files }: { label: string; files: string[] }) {
  const { t } = useTranslation();
  return (
    <>
      <span className="item-meta">{label}</span>
      {files.slice(0, FILE_PREVIEW_SIZE).map((file) => (
        <span key={`${label}-${file}`} className="item-name">{file}</span>
      ))}
      {files.length > FILE_PREVIEW_SIZE ? (
        <span className="item-meta">{t("catpartDiff.moreFiles", { count: files.length - FILE_PREVIEW_SIZE })}</span>
      ) : null}
      {!files.length ? <span className="item-meta">{t("catpartDiff.noFiles")}</span> : null}
    </>
  );
}

export function CatPartDiffResults({ result, isExporting, exportError, onExportExcel }: Props) {
  const { t } = useTranslation();
  const [visibleMatchCount, setVisibleMatchCount] = useState(GROUP_PAGE_SIZE);
  const [visibleSameCount, setVisibleSameCount] = useState(GROUP_PAGE_SIZE);
  useEffect(() => {
    setVisibleMatchCount(GROUP_PAGE_SIZE);
    setVisibleSameCount(GROUP_PAGE_SIZE);
  }, [result]);

  const hasExportRows =
    result.matches.length > 0 ||
    result.same_ge.length > 0 ||
    result.solo_a.length > 0 ||
    result.solo_b.length > 0;

  return (
    <section className="form" aria-live="polite">
      <section className="workflow-section">
        <h2 className="section-title">{t("catpartDiff.resultTitle")}</h2>
        <div className="row">
          <Badge variant="default">{t("catpartDiff.oldCount", { count: result.old_count })}</Badge>
          <Badge variant="default">{t("catpartDiff.newCount", { count: result.new_count })}</Badge>
          <Badge variant="success">{t("catpartDiff.sameGeCount", { count: result.same_ge.length })}</Badge>
          <Badge variant="warning">{t("catpartDiff.soloACount", { count: result.solo_a.length })}</Badge>
          <Badge variant="warning">{t("catpartDiff.soloBCount", { count: result.solo_b.length })}</Badge>
        </div>
        {result.status === "empty" ? <p className="hint">{t("catpartDiff.noCatparts")}</p> : null}
        {hasExportRows ? (
          <Button
            type="button"
            variant="secondary" size="sm"
            onClick={onExportExcel}
            disabled={isExporting}
          >
            {isExporting ? <Spinner aria-label={t("common.loading")} /> : null}
            {isExporting ? t("catpartDiff.exportingExcel") : t("catpartDiff.exportExcel")}
          </Button>
        ) : null}
        {exportError ? <p className="error" role="alert">{exportError}</p> : null}
      </section>

      <section className="workflow-section">
        <h3 className="section-title">{t("catpartDiff.matchesTitle")}</h3>
        <p className="hint">{t("catpartDiff.matchesDescription")}</p>
        {result.matches.length ? (
          <>
            <ul className="item-list">
              {result.matches.slice(0, visibleMatchCount).map((match) => (
                <li key={match.sin} className="item-row">
                  <Badge variant="warning">{t("catpartDiff.sinValue", { sin: match.sin })}</Badge>
                  <div className="item-main">
                    <span className="item-meta">
                      {t("catpartDiff.pnValues", { side: "A", values: match.old_pns.join(", ") })}
                    </span>
                    <span className="item-meta">
                      {t("catpartDiff.pnValues", { side: "B", values: match.new_pns.join(", ") })}
                    </span>
                    <FileList label={t("catpartDiff.oldFiles")} files={match.old_files} />
                    <FileList label={t("catpartDiff.newFiles")} files={match.new_files} />
                  </div>
                </li>
              ))}
            </ul>
            {result.matches.length > visibleMatchCount ? (
              <Button
                type="button"
                variant="ghost" size="sm"
                onClick={() => setVisibleMatchCount((count) => count + GROUP_PAGE_SIZE)}
              >
                {t("catpartDiff.showMore", { remaining: result.matches.length - visibleMatchCount })}
              </Button>
            ) : null}
          </>
        ) : (
          <p className="hint">{t("catpartDiff.noMatches")}</p>
        )}
      </section>

      <section className="workflow-section">
        <h3 className="section-title">{t("catpartDiff.sameGeTitle")}</h3>
        <p className="hint">{t("catpartDiff.sameGeDescription")}</p>
        {result.same_ge.length ? (
          <>
            <ul className="item-list">
              {result.same_ge.slice(0, visibleSameCount).map((sameGe) => (
                <li key={`${sameGe.sin}-${sameGe.pn}`} className="item-row">
                  <Badge variant="success">
                    {t("catpartDiff.sameGeValue", { sin: sameGe.sin, pn: sameGe.pn })}
                  </Badge>
                  <div className="item-main">
                    <FileList label={t("catpartDiff.oldFiles")} files={sameGe.old_files} />
                    <FileList label={t("catpartDiff.newFiles")} files={sameGe.new_files} />
                  </div>
                </li>
              ))}
            </ul>
            {result.same_ge.length > visibleSameCount ? (
              <Button
                type="button"
                variant="ghost" size="sm"
                onClick={() => setVisibleSameCount((count) => count + GROUP_PAGE_SIZE)}
              >
                {t("catpartDiff.showMore", { remaining: result.same_ge.length - visibleSameCount })}
              </Button>
            ) : null}
          </>
        ) : (
          <p className="hint">{t("catpartDiff.noSameGe")}</p>
        )}
      </section>

      {result.issues.length ? (
        <section className="workflow-section">
          <h3 className="section-title">{t("catpartDiff.issuesTitle")}</h3>
          <ul className="item-list">
            {result.issues.map((issue, index) => (
              <li key={`${issue.code}-${issue.file ?? index}`} className="item-row">
                <Badge variant="warning">{issue.code}</Badge>
                <div className="item-main">
                  {issue.file ? <span className="item-name">{issue.file}</span> : null}
                  <span className="item-meta">{issue.message}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
