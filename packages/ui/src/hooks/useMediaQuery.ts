import { useEffect, useState } from "react";

/**
 * Reactive media-query hook. SSR-safe: returns `false` on the server,
 * subscribes to `change` events on the client.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia(query);
    const listener = (event: MediaQueryListEvent): void => {
      setMatches(event.matches);
    };
    setMatches(mql.matches);
    mql.addEventListener("change", listener);
    return () => mql.removeEventListener("change", listener);
  }, [query]);

  return matches;
}
