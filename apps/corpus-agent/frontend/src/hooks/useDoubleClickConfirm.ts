import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Confirmation d'action destructrice par double-clic (jamais de pop-up natif,
 * règles CLAUDE.md #2/#13). 1er clic = arme ; 2e clic dans `timeoutMs` = exécute ;
 * sinon désarmement auto.
 */
export function useDoubleClickConfirm(onConfirm: () => void, timeoutMs = 3000) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clear = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };

  useEffect(() => clear, []);

  const handleClick = useCallback(() => {
    if (armed) {
      clear();
      setArmed(false);
      onConfirm();
      return;
    }
    setArmed(true);
    clear();
    timer.current = setTimeout(() => setArmed(false), timeoutMs);
  }, [armed, onConfirm, timeoutMs]);

  return { armed, handleClick };
}
