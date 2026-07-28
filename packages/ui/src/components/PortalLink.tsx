import { Home } from "lucide-react";

/**
 * "Back to portal" link. When a POC is deployed under a shared parent path
 * (e.g. `/app/atexispocs-cd/corpus-agent/`), the portal landing page lives at
 * the PARENT path (`/app/atexispocs-cd/`). We derive it from the app's build
 * base URL, so no server host / IP is ever hard-coded — the same bundle points
 * back to whatever parent it was mounted under.
 *
 * Renders nothing in local dev, where the base is `/` (root has no parent, so
 * there is no portal to return to). Drop it once in the app shell (sidebar).
 */

/**
 * Parent path of a base URL, or `null` when the base is the site root.
 * `"/app/atexispocs-cd/corpus-agent/"` -> `"/app/atexispocs-cd/"`;
 * `"/corpus-agent/"` -> `"/"`; `"/"` or `""` -> `null`.
 */
export function portalHref(base: string): string | null {
  const trimmed = base.replace(/\/+$/, "");
  if (!trimmed) return null; // base was "/" -> at root, no parent portal
  return trimmed.slice(0, trimmed.lastIndexOf("/") + 1) || null;
}

/** Vite injects `import.meta.env.BASE_URL` at build time in the consuming app. */
function currentBase(): string {
  const env = (import.meta as unknown as { env?: { BASE_URL?: string } }).env;
  return env?.BASE_URL ?? "/";
}

export type PortalLinkProps = {
  /** Accessible label / tooltip, e.g. `t("nav.portal")`. Rendered as a house
   *  icon only, so this is the `aria-label` and `title`, not visible text. */
  label: string;
  /** Override the app base path (defaults to the built `VITE_BASE`). */
  base?: string;
  className?: string;
};

export function PortalLink({ label, base, className }: PortalLinkProps) {
  const href = portalHref(base ?? currentBase());
  if (!href) return null;

  return (
    <a href={href} className={className} data-portal-link aria-label={label} title={label}>
      <Home size={16} aria-hidden="true" />
    </a>
  );
}
