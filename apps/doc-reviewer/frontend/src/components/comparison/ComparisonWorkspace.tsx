import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  comparisonApi,
  type ComparisonDetail,
  type ComparisonPair,
} from "../../lib/comparisonApi";
import { ComparisonAlignmentStatus, ComparisonPagePane } from "./ComparisonPagePane";
import "../../styles/comparison.css";
import "../../styles/comparison-pages.css";

export function ComparisonWorkspace({
  comparison,
  language,
  onSelectDifference,
}: {
  comparison: ComparisonDetail;
  language: "fr" | "en";
  onSelectDifference: (selection: { documentIndex: number; groupId: string } | null) => void;
}) {
  const { t } = useTranslation();
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [pageIndex, setPageIndex] = useState(0);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [transitionFrom, setTransitionFrom] = useState<number | null>(null);
  const transitionTimer = useRef<number | null>(null);
  const pairs = comparison.report.comparisons;
  const slots = comparison.report.page_slots;
  const activeIndex = Math.min(candidateIndex, Math.max(0, pairs.length - 1));
  const activePair = pairs[activeIndex];
  const slot = slots[pageIndex];
  const alignment = activePair?.page_alignment.find((item) => item.slot_id === slot?.id);
  const reference = comparison.report.documents[comparison.report.reference_index];

  useEffect(() => {
    if (transitionTimer.current !== null) window.clearTimeout(transitionTimer.current);
    transitionTimer.current = null;
    setCandidateIndex(0);
    setPageIndex(0);
    setSelectedGroupId(null);
    setTransitionFrom(null);
    onSelectDifference(null);
  }, [comparison.id, onSelectDifference]);
  useEffect(
    () => () => {
      if (transitionTimer.current !== null) window.clearTimeout(transitionTimer.current);
    },
    [],
  );

  const changeCandidate = (nextIndex: number) => {
    if (nextIndex === activeIndex || transitionTimer.current !== null) return;
    setTransitionFrom(activeIndex);
    setCandidateIndex(nextIndex);
    setSelectedGroupId(null);
    onSelectDifference(null);
    transitionTimer.current = window.setTimeout(() => {
      setTransitionFrom(null);
      transitionTimer.current = null;
    }, 360);
  };
  const changePage = (nextIndex: number) => {
    setPageIndex(nextIndex);
    setSelectedGroupId(null);
    onSelectDifference(null);
  };
  const selectGroup = (groupId: string) => {
    setSelectedGroupId(groupId);
    if (activePair) onSelectDifference({ documentIndex: activePair.document_index, groupId });
  };
  const referenceUnavailable = slot
    ? t("comparison.pageMissingInReference")
    : t("comparison.noAlignment");
  const comparisonUnavailable = !slot
    ? t("comparison.noAlignment")
    : !alignment && slot.reference_page === null
      ? t("comparison.pageSlotFromOtherVersion")
      : t("comparison.pageMissingInVersion");
  const renderCandidatePane = (
    pair: ComparisonPair,
    index: number,
    className: string,
  ) => {
    const pageMatch = pair.page_alignment.find((item) => item.slot_id === slot?.id);
    return (
      <div key={`${pair.document_index}-${index}`} className={className}>
        <ComparisonPagePane
          comparisonId={comparison.id}
          documentIndex={pair.document_index}
          filename={pair.filename}
          pageNumber={pageMatch?.comparison_page ?? null}
          side="comparison"
          changes={pair.changes}
          selectedGroupId={selectedGroupId}
          unavailableMessage={pageMatch?.comparison_page === null ? t("comparison.pageMissingInVersion") : comparisonUnavailable}
          onSelectGroup={selectGroup}
        />
      </div>
    );
  };

  return (
    <div className="comparison-workspace">
      <div className="comparison-workspace-controls">
        <nav className="comparison-page-control" aria-label={t("comparison.pageControlsLabel")}>
          <button
            type="button"
            className="btn secondary small"
            aria-label={t("comparison.previousPage")}
            disabled={pageIndex <= 0}
            onClick={() => changePage(pageIndex - 1)}
          >
            <ChevronLeft size={16} aria-hidden="true" />
          </button>
          <span aria-live="polite">
            {slots.length
              ? t("comparison.pagePosition", { current: pageIndex + 1, total: slots.length })
              : t("comparison.noAlignment")}
          </span>
          <button
            type="button"
            className="btn secondary small"
            aria-label={t("comparison.nextPage")}
            disabled={pageIndex >= slots.length - 1}
            onClick={() => changePage(pageIndex + 1)}
          >
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </nav>
        {pairs.length > 1 && activePair ? (
          <nav className="comparison-candidate-control" aria-label={t("comparison.candidateControlsLabel")}>
            <button
              type="button"
              className="btn secondary small"
              aria-label={t("comparison.previousCandidate")}
              disabled={activeIndex === 0 || transitionTimer.current !== null}
              onClick={() => changeCandidate(activeIndex - 1)}
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <label className="label" htmlFor="comparison-candidate">
              {t("comparison.candidateCounter", { current: activeIndex + 1, total: pairs.length })}
            </label>
            <select
              id="comparison-candidate"
              className="input"
              value={activeIndex}
              disabled={transitionTimer.current !== null}
              onChange={(event) => changeCandidate(Number(event.target.value))}
            >
              {pairs.map((pair, index) => <option key={pair.document_index} value={index}>{pair.filename}</option>)}
            </select>
            <button
              type="button"
              className="btn secondary small"
              aria-label={t("comparison.nextCandidate")}
              disabled={activeIndex >= pairs.length - 1 || transitionTimer.current !== null}
              onClick={() => changeCandidate(activeIndex + 1)}
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
            <a className="btn ghost small" href={comparisonApi.exportDocumentUrl(comparison.id, activePair.document_index, language)} download>
              {t("comparison.exportOne")}
            </a>
          </nav>
        ) : null}
      </div>

      <ComparisonAlignmentStatus slot={slot} alignment={alignment} />
      <div className="comparison-split-view">
        <ComparisonPagePane
          comparisonId={comparison.id}
          documentIndex={comparison.report.reference_index}
          filename={reference?.filename ?? comparison.title}
          pageNumber={slot?.reference_page ?? null}
          side="reference"
          changes={activePair?.changes ?? []}
          selectedGroupId={selectedGroupId}
          unavailableMessage={referenceUnavailable}
          onSelectGroup={selectGroup}
        />
        <div className="comparison-switcher">
          {transitionFrom !== null && pairs[transitionFrom]
            ? renderCandidatePane(pairs[transitionFrom], transitionFrom, "comparison-switcher__layer comparison-switcher__layer--outgoing")
            : null}
          {activePair
            ? renderCandidatePane(activePair, activeIndex, `comparison-switcher__layer${transitionFrom !== null ? " comparison-switcher__layer--incoming" : ""}`)
            : null}
        </div>
      </div>
    </div>
  );
}
