import { Button, Card, CardContent, Checkbox, Select } from "@internal/ui";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { WizardDm } from "../../lib/api";
import {
  isReviewable, procedureCategories, reviewDestinations, type PreliminaryState, type ReviewPassage,
} from "../../lib/preliminaryTypes";
import { usePreliminaryReview } from "../../lib/usePreliminaryReview";
import { PreliminaryPassage } from "./PreliminaryPassage";
import { ProcedureReader } from "./ProcedureReader";

type Props = {
  docId: string;
  initial: PreliminaryState;
  dms: WizardDm[];
  busy: boolean;
  onBack: () => void;
  onGenerate: () => void;
  onFlushReady: (flush: (() => Promise<boolean>) | null) => void;
};

export function PreliminaryReview({ docId, initial, dms, busy, onBack, onGenerate, onFlushReady }: Props) {
  const { t } = useTranslation();
  const review = usePreliminaryReview(docId, initial);
  const procedures = dms.filter((dm) => dm.dm_type === "procedural");
  const [active, setActive] = useState(initial.active_dm_id ?? procedures[0]?.dm_id ?? "");
  const current = review.state.reviews[active];
  const [selectedId, setSelectedId] = useState(current?.position.selected_id ?? null);
  const [jump, setJump] = useState(0);
  const [readerEpoch, setReaderEpoch] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const [filter, setFilter] = useState("all");
  const [restartArmed, setRestartArmed] = useState(false);
  const [reloadArmed, setReloadArmed] = useState(false);
  const [skipArmed, setSkipArmed] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout>>();
  const skipTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    onFlushReady(() => review.flush());
    return () => onFlushReady(null);
  }, [onFlushReady, review.flush]);
  useEffect(() => () => {
    clearTimeout(armTimer.current);
    clearTimeout(skipTimer.current);
  }, []);
  if (!current) return <p role="alert">{t("preliminary.unavailable")}</p>;
  const index = procedures.findIndex((dm) => dm.dm_id === active);
  const disabled = busy || review.saving || Boolean(review.error);
  const stale = current.status === "stale";
  const passages = current.passages.filter(isReviewable);
  const undecided = passages.filter((item) => !item.decision).length;
  const matchesFilter = (passage: ReviewPassage) =>
    filter === "all" || (filter === "pending"
      ? !passage.decision
      : passage.decision === filter || (!passage.decision && passage.suggested === filter));
  const complete = Object.values(review.state.reviews).every(
    (item) => item.status === "reviewed" || item.status === "skipped",
  );

  const changeProcedure = async (id: string) => {
    if (!await review.flush()) return;
    const target = review.state.reviews[id];
    if (!target) return;
    if (target.status !== "stale" && !await review.act({
      op: "cursor", dm_id: id, ...target.position,
    })) return;
    setActive(id);
    setSelectedId(target.position.selected_id);
    setJump(0);
    setConfirmed(false);
    setRestartArmed(false);
    setSkipArmed(false);
    clearTimeout(skipTimer.current);
  };
  const completeProcedure = async () => {
    if (!await review.act({ dm_id: active, op: "complete", confirm_empty: confirmed })) return;
    const next = procedures.slice(index + 1).concat(procedures.slice(0, index)).find((dm) => {
      if (dm.dm_id === active) return false;
      const status = review.state.reviews[dm.dm_id]?.status;
      return status !== "reviewed" && status !== "skipped";
    });
    if (next) await changeProcedure(next.dm_id);
  };
  const skipReviews = async () => {
    if (!skipArmed) {
      setSkipArmed(true);
      skipTimer.current = setTimeout(() => setSkipArmed(false), 3000);
      return;
    }
    clearTimeout(skipTimer.current);
    setSkipArmed(false);
    if (await review.act({ dm_id: active, op: "skip" })) onGenerate();
  };
  const savedLabel = review.error ? "saveFailed"
    : review.saving || review.dirty ? "saving" : current.saved_at ? "saved" : "notReviewed";
  return (
    <Card>
      <CardContent className="space-y-4 pt-4">
        <h2 className="font-display text-lg">{t("preliminary.title")}</h2>
        <p className="text-sm text-fg-dim">{t("preliminary.localOnly")}</p>
        <div className="flex flex-wrap gap-3 items-center">
          <strong>{t("preliminary.progress", { current: index + 1, total: procedures.length })}</strong>
          <span>{t(`preliminary.status.${current.status}`)}</span>
          <span role="status" aria-live="polite">{t(`preliminary.${savedLabel}`)}</span>
          {current.saved_at ? <time dateTime={current.saved_at}>{new Date(current.saved_at).toLocaleTimeString()}</time> : null}
        </div>
        {review.error ? (
          <div role="alert" className="border border-danger rounded-sm p-3 space-y-3">
            <p>{t("preliminary.saveFailed")}: {review.error}</p>
            <div className="flex gap-3 flex-wrap">
              <Button variant="secondary" disabled={review.saving} onClick={() => void review.retry()}>
                {t("preliminary.retry")}
              </Button>
              <Button variant="secondary" disabled={review.saving} onClick={() => {
                if (!reloadArmed) {
                  setReloadArmed(true);
                  armTimer.current = setTimeout(() => setReloadArmed(false), 3000);
                } else {
                  setReloadArmed(false);
                  void review.reload().then((next) => {
                    if (!next?.active_dm_id) return;
                    setActive(next.active_dm_id);
                    setSelectedId(next.reviews[next.active_dm_id]?.position.selected_id ?? null);
                    setJump(0);
                    setConfirmed(false);
                    setReaderEpoch((value) => value + 1);
                  });
                }
              }}>{t(reloadArmed ? "preliminary.confirmAgain" : "preliminary.reload")}</Button>
            </div>
          </div>
        ) : null}
        {review.state.source_changed ? <p className="text-warning">{t("preliminary.sourceChanged")}</p> : null}
        <label className="block">
          <span>{t("preliminary.procedure")}</span>
          <Select aria-label={t("preliminary.procedure")} value={active} disabled={disabled}
            options={procedures.map((dm) => ({ value: dm.dm_id, label: dm.title }))}
            onChange={(event) => void changeProcedure(event.target.value)} />
        </label>
        <div className="flex gap-3 flex-wrap">
          <Button variant="secondary" disabled={disabled || index <= 0}
            onClick={() => void changeProcedure(procedures[index - 1]!.dm_id)}>{t("preliminary.previous")}</Button>
          <Button variant="secondary" disabled={disabled || index >= procedures.length - 1}
            onClick={() => void changeProcedure(procedures[index + 1]!.dm_id)}>{t("preliminary.next")}</Button>
        </div>
        {stale ? (
          <div role="alert" className="space-y-3">
            <p>{t("preliminary.staleHelp")}</p>
            <Button disabled={disabled} variant="danger" onClick={() => {
              if (!restartArmed) {
                setRestartArmed(true);
                armTimer.current = setTimeout(() => setRestartArmed(false), 3000);
              } else {
                setRestartArmed(false);
                void review.act({ dm_id: active, op: "restart" }).then((saved) => {
                  if (saved) { setSelectedId(null); setJump(0); }
                });
              }
            }}>{t(restartArmed ? "preliminary.confirmAgain" : "preliminary.restart")}</Button>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-3 text-sm text-fg-dim">
              <p className="w-full">{t("preliminary.confirmationHelp")}</p>
              <p className="w-full">{t("preliminary.structureHelp", { count: current.passages.length - passages.length })}</p>
              {procedureCategories.map((category) => (
                <span key={category}>{t(`preliminary.category.${category}`)}:{" "}
                  {passages.filter((p) => p.decision === category).length}</span>
              ))}
            </div>
            <div className="grid gap-4 min-w-0 lg:grid-cols-2 lg:items-stretch">
              <ProcedureReader key={`${active}:${current.fingerprint}:${readerEpoch}`} docId={docId} dmId={active} review={current}
                sourceFormat={review.state.source_format} selectedId={selectedId} jump={jump}
                onPosition={(value) => review.position(active, value)} />
              <section className="min-w-0 space-y-3" aria-label={t("preliminary.classification")}>
                <label className="block">
                  <span>{t("preliminary.filter")}</span>
                  <Select aria-label={t("preliminary.filter")} value={filter}
                    options={["all", "pending", ...reviewDestinations].map((value) => ({
                      value, label: t(`preliminary.category.${value}`),
                    }))} onChange={(event) => setFilter(event.target.value)} />
                </label>
                <p>{t("preliminary.remaining", { count: undecided, total: passages.length })}</p>
                <div data-testid="passage-list" className="h-96 lg:h-[70vh] overflow-y-auto space-y-3 pr-2">
                  {passages.filter(matchesFilter)
                    .map((passage) => (
                      <PreliminaryPassage key={passage.id} dmId={active} passage={passage}
                        text={review.edits[passage.id] ?? passage.text}
                        disabled={disabled} editDisabled={busy} selected={selectedId === passage.id}
                        onSelect={() => { setSelectedId(passage.id); setJump((n) => n + 1); }}
                        onAction={async (action) => {
                          const saved = await review.act(action);
                          if (saved && action.op === "split") { setSelectedId(null); setJump(0); }
                          return saved;
                        }} onEdit={review.edit} />
                    ))}
                  {!passages.length ? <p>{t("preliminary.noPassages")}</p> : null}
                </div>
                <div className="flex gap-3 items-start">
                  <Checkbox checked={confirmed} disabled={disabled}
                    aria-label={t("preliminary.confirmWhole")} onCheckedChange={setConfirmed} />
                  <span>{t("preliminary.confirmWhole")}</span>
                </div>
                <Button disabled={disabled || review.dirty || undecided > 0 || !confirmed || current.status === "reviewed"}
                  onClick={() => void completeProcedure()}>
                  {t("preliminary.complete")}
                </Button>
              </section>
            </div>
          </>
        )}
        <div className="flex flex-wrap gap-3 justify-between">
          <Button variant="secondary" disabled={disabled} onClick={onBack}>{t("common.back")}</Button>
          <div className="space-y-2">
        <p className="max-w-xl text-sm text-fg-dim">{t("preliminary.skipHelp")}</p>
        <Button variant="secondary" disabled={disabled || review.dirty} onClick={() => void skipReviews()}>
          {t(skipArmed ? "preliminary.skipConfirm" : "preliminary.skip")}
        </Button>
          </div>
          <Button disabled={disabled || !complete || review.dirty} onClick={onGenerate}>
        {t("preliminary.generate")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
