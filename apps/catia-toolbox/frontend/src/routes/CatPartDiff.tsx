import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox } from "@internal/ui";

import { FilePicker } from "../components/FilePicker";
import { ApiClientError } from "../lib/api";
import { catpartDiffApi, type CatpartCandidateDto } from "../lib/catpartApi";

const UNMATCHED_PAGE_SIZE = 100;

export function CatPartDiff() {
  const { t } = useTranslation();
  const [oldPath, setOldPath] = useState("");
  const [newPath, setNewPath] = useState("");
  const [includeGeometry, setIncludeGeometry] = useState(false);
  const [confirmedPairs, setConfirmedPairs] = useState<CatpartCandidateDto[]>([]);
  const [visibleOldCount, setVisibleOldCount] = useState(UNMATCHED_PAGE_SIZE);
  const [visibleNewCount, setVisibleNewCount] = useState(UNMATCHED_PAGE_SIZE);
  const mutation = useMutation({
    mutationFn: () => catpartDiffApi.compare(oldPath, newPath, includeGeometry),
    onSuccess: () => {
      setConfirmedPairs([]);
      setVisibleOldCount(UNMATCHED_PAGE_SIZE);
      setVisibleNewCount(UNMATCHED_PAGE_SIZE);
    },
  });
  const result = mutation.data;
  const exactOldCount = result?.exact.old_files ?? 0;
  const exactNewCount = result?.exact.new_files ?? 0;
  const fileIssues = (result?.issues ?? []).filter((issue) => issue.file !== null);

  const toggleConfirmation = (candidate: CatpartCandidateDto, confirmed: boolean) => {
    setConfirmedPairs((current) =>
      confirmed
        ? current.filter((pair) => pair.old_file !== candidate.old_file || pair.new_file !== candidate.new_file)
        : [...current, candidate],
    );
  };

  return (
    <div className="form">
      <article className="card">
        <h2 className="card-title">{t("catpartDiff.title")}</h2>
        <p className="hint">{t("catpartDiff.description")}</p>
        <p className="hint">{t("catpartDiff.limit")}</p>
        <p className="hint">{t("catpartDiff.geometryToggleHint")}</p>
        <div className="row">
          <div className="field grow">
            <span className="field-label">{t("catpartDiff.oldFolder")}</span>
            <FilePicker
              mode="folder"
              scope="input"
              exts={[".CATPart"]}
              value={oldPath}
              onChange={setOldPath}
              label={t("catpartDiff.selectFolder")}
            />
          </div>
          <div className="field grow">
            <span className="field-label">{t("catpartDiff.newFolder")}</span>
            <FilePicker
              mode="folder"
              scope="input"
              exts={[".CATPart"]}
              value={newPath}
              onChange={setNewPath}
              label={t("catpartDiff.selectFolder")}
            />
          </div>
          <button
            type="button"
            className="btn primary"
            onClick={() => mutation.mutate()}
            disabled={!oldPath || !newPath || mutation.isPending}
          >
            {mutation.isPending ? <span className="spinner" /> : null}
            {mutation.isPending ? t("catpartDiff.analyzing") : t("catpartDiff.compare")}
          </button>
        </div>
        <label className="row">
          <Checkbox
            checked={includeGeometry}
            onCheckedChange={(checked) => setIncludeGeometry(checked === true)}
            aria-label={t("catpartDiff.geometryToggle")}
          />
          <span>{t("catpartDiff.geometryToggle")}</span>
        </label>
        {mutation.isError ? (
          <p className="error" role="alert">
            {mutation.error instanceof ApiClientError ? mutation.error.message : t("catpartDiff.errorFallback")}
          </p>
        ) : null}
      </article>

      {result ? (
        <section className="form" aria-live="polite">
          <article className="card">
            <h2 className="card-title">{t("catpartDiff.title")}</h2>
            <p className="hint" role="status">
              {t(`catpartDiff.geometryStatus.${result.geometry_status}`)}
            </p>
            <div className="row">
              <span className="badge default">{t("catpartDiff.oldCount", { count: result.old_count })}</span>
              <span className="badge default">{t("catpartDiff.newCount", { count: result.new_count })}</span>
            </div>
            <p className="hint">
              {exactOldCount || exactNewCount
                ? t("catpartDiff.exactSkipped", {
                    groups: result.exact.groups,
                    oldCount: exactOldCount,
                    newCount: exactNewCount,
                  })
                : t("catpartDiff.exactNone")}
            </p>
            {result.status === "empty" ? <p className="hint">{t("catpartDiff.noCatparts")}</p> : null}
          </article>

          <article className="card">
            <h3 className="card-title">{t("catpartDiff.candidateTitle")}</h3>
            <p className="hint">{t("catpartDiff.candidateDescription")}</p>
            {result.candidates.length ? (
              <ul className="item-list">
                {result.candidates.map((candidate) => {
                  const confirmed = confirmedPairs.some(
                    (pair) => pair.old_file === candidate.old_file && pair.new_file === candidate.new_file,
                  );
                  const conflict =
                    !confirmed &&
                    confirmedPairs.some(
                      (pair) => pair.old_file === candidate.old_file || pair.new_file === candidate.new_file,
                    );
                  return (
                    <li key={`${candidate.old_file}\u001f${candidate.new_file}`} className="item-row">
                      <span className={`badge ${confirmed ? "ok" : "warn"}`}>
                        {confirmed ? t("catpartDiff.pairConfirmed") : t("catpartDiff.lowConfidence")}
                      </span>
                      <div className="item-main">
                        <span className="item-name">{`${t("catpartDiff.oldFiles")}: ${candidate.old_file}`}</span>
                        <span className="item-name">{`${t("catpartDiff.newFiles")}: ${candidate.new_file}`}</span>
                        <span className="item-meta">
                          {t("catpartDiff.candidateScore", { score: candidate.similarity.toFixed(1) })}
                          {" · "}
                          {candidate.old_geometry_quality === "complete" && candidate.new_geometry_quality === "complete"
                            ? t("catpartDiff.completeGeometry")
                            : t("catpartDiff.partialGeometry")}
                        </span>
                        {confirmed ? <span className="badge warn">{t("catpartDiff.binaryChanged")}</span> : null}
                        {conflict ? <span className="error">{t("catpartDiff.pairConflict")}</span> : null}
                      </div>
                      <button
                        type="button"
                        className={`btn small ${confirmed ? "secondary" : "ghost"}`}
                        disabled={conflict}
                        onClick={() => toggleConfirmation(candidate, confirmed)}
                      >
                        {confirmed ? t("catpartDiff.unconfirmPair") : t("catpartDiff.confirmPair")}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="hint">{t("catpartDiff.noCandidates")}</p>
            )}
          </article>

          {result.unmatched_old.length || result.unmatched_new.length ? (
            <article className="card">
              <h3 className="card-title">{t("catpartDiff.unmatchedTitle")}</h3>
              <p className="hint">{t("catpartDiff.unmatchedDescription")}</p>
              <ul className="item-list">
                {result.unmatched_old.slice(0, visibleOldCount).map((file) => (
                  <li key={`old-${file}`} className="item-row">
                    <span className="item-name">{`${t("catpartDiff.oldFiles")}: ${file}`}</span>
                  </li>
                ))}
                {result.unmatched_new.slice(0, visibleNewCount).map((file) => (
                  <li key={`new-${file}`} className="item-row">
                    <span className="item-name">{`${t("catpartDiff.newFiles")}: ${file}`}</span>
                  </li>
                ))}
              </ul>
              {result.unmatched_old.length > visibleOldCount ? (
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => setVisibleOldCount((count) => count + UNMATCHED_PAGE_SIZE)}
                >
                  {t("catpartDiff.showMore", { remaining: result.unmatched_old.length - visibleOldCount })}
                </button>
              ) : null}
              {result.unmatched_new.length > visibleNewCount ? (
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => setVisibleNewCount((count) => count + UNMATCHED_PAGE_SIZE)}
                >
                  {t("catpartDiff.showMore", { remaining: result.unmatched_new.length - visibleNewCount })}
                </button>
              ) : null}
            </article>
          ) : null}

          {fileIssues.length ? (
            <article className="card">
              <h3 className="card-title">{t("catpartDiff.issuesTitle")}</h3>
              <ul className="item-list">
                {fileIssues.map((issue, index) => (
                  <li key={`${issue.code}-${issue.file ?? index}`} className="item-row">
                    <span className="badge warn">{issue.code}</span>
                    <div className="item-main">
                      {issue.file ? <span className="item-name">{issue.file}</span> : null}
                      <span className="item-meta">{issue.message}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </section>
      ) : (
        <div className="empty-state">
          <h3 className="card-title">{t("catpartDiff.runPrompt")}</h3>
        </div>
      )}
    </div>
  );
}
