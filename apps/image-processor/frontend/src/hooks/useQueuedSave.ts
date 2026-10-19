import { useCallback, useEffect, useRef, useState } from "react";

export function useQueuedSave<T>(value: T | null, save: (value: T) => Promise<unknown>) {
  const pending = useRef<T | null>(null);
  const running = useRef<Promise<void> | null>(null);
  const saveRef = useRef(save);
  const failure = useRef<unknown>(null);
  const mounted = useRef(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(0);
  saveRef.current = save;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const flush = useCallback(async () => {
    if (running.current) {
      await running.current;
      if (failure.current) throw failure.current;
      return;
    }
    const write = async () => {
      if (mounted.current) {
        setSaving(true);
        setError(null);
      }
      failure.current = null;
      while (pending.current !== null) {
        const next = pending.current;
        pending.current = null;
        try {
          await saveRef.current(next);
          if (mounted.current) setSaved((count) => count + 1);
        } catch (saveError) {
          pending.current ??= next;
          failure.current = saveError;
          if (mounted.current) setError(saveError);
          break;
        }
      }
      if (mounted.current) setSaving(false);
    };
    running.current = write();
    await running.current;
    running.current = null;
    if (failure.current) throw failure.current;
  }, []);

  useEffect(() => {
    if (value === null) return;
    pending.current = value;
    void flush().catch(() => {
      // The failed snapshot is retained and the error is exposed for retry.
    });
  }, [value, flush]);

  return { saving, error, saved, flush };
}
