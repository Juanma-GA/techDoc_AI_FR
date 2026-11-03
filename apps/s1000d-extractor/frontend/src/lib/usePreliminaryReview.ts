import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { preliminaryApi } from "./preliminaryApi";
import { ApiRequestError } from "./api";
import { formatApiError } from "./migrationUtils";
import type { PreliminaryState, ReaderPosition, ReviewAction } from "./preliminaryTypes";
import { preliminaryRulesApi, preliminaryRulesQueryKey } from "./preliminaryRules";

export function usePreliminaryReview(docId: string, initial: PreliminaryState) {
  const { t } = useTranslation();
  const translation = useRef(t);
  translation.current = t;
  const rules = useQuery({
    queryKey: preliminaryRulesQueryKey, queryFn: preliminaryRulesApi.read, enabled: false,
  }).data;
  const [state, setState] = useState(initial);
  const latest = useRef(initial);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const failed = useRef<ReviewAction | null>(null);
  const invalid = useRef(false);
  const cursor = useRef<ReviewAction | null>(null);
  const drafts = useRef(new Map<string, ReviewAction>());
  const [edits, setEdits] = useState<Record<string, string>>({});
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const queue = useRef<Promise<boolean>>(Promise.resolve(true));
  const pending = useRef(0);

  const enqueue = useCallback((action: ReviewAction, keepalive = false) => {
    pending.current += 1;
    setSaving(true);
    const result = queue.current.then(async () => {
      if (failed.current) return false;
      try {
        const next = await preliminaryApi.save(docId, latest.current.revision, action, keepalive);
        latest.current = next;
        setState(next);
        setError(null);
        return true;
      } catch (reason) {
        failed.current = action;
        invalid.current = reason instanceof ApiRequestError && reason.status === 422;
        setError(formatApiError(translation.current, reason));
        return false;
      }
    }).finally(() => {
      pending.current -= 1;
      setSaving(pending.current > 0);
    });
    queue.current = result;
    return result;
  }, [docId]);

  const flush = useCallback(async (keepalive = false) => {
    clearTimeout(timer.current);
    for (const [key, draft] of drafts.current) {
      if (!await enqueue(draft, keepalive)) return false;
      if (drafts.current.get(key) === draft) {
        drafts.current.delete(key);
        setEdits((current) => {
          const next = { ...current };
          delete next[key];
          return next;
        });
      }
    }
    const action = cursor.current;
    cursor.current = null;
    if (action) {
      const saved = await enqueue(action, keepalive);
      if (!saved) {
        cursor.current = action;
        return false;
      }
    }
    const saved = await queue.current;
    setDirty(Boolean(cursor.current || failed.current || drafts.current.size));
    return saved && !failed.current;
  }, [enqueue]);

  const edit = useCallback((action: ReviewAction & { passage_id: string; text: string }) => {
    if (invalid.current && failed.current?.passage_id === action.passage_id) {
      failed.current = null;
      invalid.current = false;
      setError(null);
    }
    drafts.current.set(action.passage_id, action);
    setEdits((current) => ({ ...current, [action.passage_id]: action.text }));
    setDirty(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, 500);
  }, [flush]);

  const position = useCallback((dmId: string, value: ReaderPosition) => {
    cursor.current = { dm_id: dmId, op: "cursor", ...value };
    setDirty(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, 300);
  }, [flush]);

  const act = useCallback(async (action: ReviewAction) => {
    if (!await flush()) return false;
    return enqueue(action);
  }, [enqueue, flush]);

  const retry = useCallback(async () => {
    const action = failed.current;
    failed.current = null;
    if (action && !await enqueue(action)) return false;
    return flush();
  }, [enqueue, flush]);

  const reload = useCallback(async () => {
    setSaving(true);
    try {
      const next = await preliminaryApi.read(docId);
      latest.current = next;
      setState(next);
      failed.current = null;
      cursor.current = null;
      drafts.current.clear();
      setEdits({});
      setDirty(false);
      setError(null);
      return next;
    } catch (reason) {
      setError(formatApiError(translation.current, reason));
      return null;
    } finally {
      setSaving(false);
    }
  }, [docId]);

  useEffect(() => {
    const hide = () => {
      if (document.visibilityState === "hidden") void flush(true);
    };
    const leave = (event: BeforeUnloadEvent) => {
      if (cursor.current || pending.current || failed.current || drafts.current.size) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    document.addEventListener("visibilitychange", hide);
    window.addEventListener("beforeunload", leave);
    return () => {
      clearTimeout(timer.current);
      document.removeEventListener("visibilitychange", hide);
      window.removeEventListener("beforeunload", leave);
      void flush(true);
    };
  }, [flush]);

  const outdated = (review: PreliminaryState["reviews"][string]) =>
    rules !== undefined && review.rules_revision !== undefined && rules.revision > review.rules_revision;
  const displayed = rules && Object.values(state.reviews).some(outdated) ? {
    ...state, source_changed: true,
    reviews: Object.fromEntries(Object.entries(state.reviews).map(([id, review]) => [
      id, outdated(review) ? { ...review, status: "stale" as const } : review,
    ])),
  } : state;
  return { state: displayed, saving, dirty, error, edits, edit, act, position, flush, retry, reload };
}
