import { useEffect, useState, useCallback } from 'react';
import { fetchHealth } from '../services/api';

/**
 * Polls `/api/v1/health` for the LLM badge (STANDARD_POC.md rule #13).
 */
export function useHealth() {
  const [data, setData] = useState(null);

  const refresh = useCallback(() => {
    fetchHealth().then(setData).catch(() => setData(null));
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  return { data, refresh };
}
