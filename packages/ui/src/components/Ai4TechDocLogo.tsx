import { cn } from "../lib/utils";
import { useSyncExternalStore } from "react";

const iconUrl = new URL("../assets/ai4techdoc.svg", import.meta.url).href;
const faviconSelector = 'link[data-ai4techdoc-favicon="true"]';
const faviconSize = 128;

type AppTheme = "light" | "dark";

let faviconObserver: MutationObserver | undefined;
let faviconGeneration = 0;

function getAppTheme(): AppTheme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function subscribeToAppTheme(onChange: () => void): () => void {
  if (typeof document === "undefined") return () => {};
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

function useAppTheme(): AppTheme {
  return useSyncExternalStore(subscribeToAppTheme, getAppTheme, () => "light");
}

function renderFavicon(favicon: HTMLLinkElement, theme: AppTheme): void {
  const generation = ++faviconGeneration;
  const image = new Image();
  image.style.colorScheme = theme;
  image.style.position = "absolute";
  image.style.left = "-10000px";
  image.style.width = `${faviconSize}px`;
  image.style.height = `${faviconSize}px`;
  image.style.visibility = "hidden";
  image.setAttribute("aria-hidden", "true");
  image.onload = () => {
    if (generation !== faviconGeneration || !favicon.isConnected) {
      image.remove();
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = faviconSize;
    canvas.height = faviconSize;
    const context = canvas.getContext("2d");
    if (!context) {
      image.remove();
      return;
    }

    try {
      context.drawImage(image, 0, 0, faviconSize, faviconSize);
      favicon.type = "image/png";
      favicon.href = canvas.toDataURL("image/png");
    } catch {
      favicon.type = "image/svg+xml";
      favicon.href = iconUrl;
    } finally {
      image.remove();
    }
  };
  image.onerror = () => {
    image.remove();
    if (generation !== faviconGeneration || !favicon.isConnected) return;
    favicon.type = "image/svg+xml";
    favicon.href = iconUrl;
  };
  document.body.append(image);
  image.src = iconUrl;
}

export function setAi4TechDocFavicon(): () => void {
  const favicon =
    document.querySelector<HTMLLinkElement>(faviconSelector) ??
    document.querySelector<HTMLLinkElement>('link[rel="icon"]') ??
    document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = iconUrl;
  favicon.dataset.ai4techdocFavicon = "true";
  if (!favicon.isConnected) document.head.append(favicon);

  faviconObserver?.disconnect();
  const observer = new MutationObserver(() => renderFavicon(favicon, getAppTheme()));
  faviconObserver = observer;
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  renderFavicon(favicon, getAppTheme());

  return () => {
    if (faviconObserver !== observer) return;
    observer.disconnect();
    faviconObserver = undefined;
    faviconGeneration += 1;
  };
}

export type Ai4TechDocLogoProps = {
  alt?: string;
  className?: string;
};

export function Ai4TechDocLogo({ alt = "AI4TECHDOC", className }: Ai4TechDocLogoProps) {
  const theme = useAppTheme();
  return (
    <img
      src={iconUrl}
      alt={alt}
      style={{ colorScheme: theme }}
      className={cn("block h-7 w-7 shrink-0 self-center object-contain", className)}
    />
  );
}