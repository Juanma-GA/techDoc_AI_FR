import { useCallback, useEffect, useRef, useState } from "react";

// Confirmation des actions destructrices par double-clic (regle CLAUDE.md #13) :
// le 1er clic arme la cle, le 2e clic dans les 3 s execute l'action.
export function useArmedConfirm(delayMs = 3000) {
  const [armed, setArmed] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const trigger = useCallback(
    (key: string, action: () => void) => {
      if (timer.current) clearTimeout(timer.current);
      if (armed === key) {
        setArmed(null);
        action();
        return;
      }
      setArmed(key);
      timer.current = setTimeout(() => setArmed(null), delayMs);
    },
    [armed, delayMs],
  );

  return { armed, trigger };
}
