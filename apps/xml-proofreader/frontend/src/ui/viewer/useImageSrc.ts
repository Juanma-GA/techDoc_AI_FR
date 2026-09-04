// Resolves a figure's image reference to a displayable URL (data:/asset),
// relative to the open document. Cached by the resolver; falls back to null
// (the viewer shows a placeholder) when the image can't be read.
import { useEffect, useState } from "react";
import { createResource } from "../../adapters";
import { ResourceResolver } from "../../core/resources/resolver";
import { useStore } from "../store";

const resolver = new ResourceResolver(createResource());

function immediate(href: string | null): string | null {
  return href && (href.startsWith("data:") || /^https?:\/\//i.test(href)) ? href : null;
}

export function useImageSrc(href: string | null): string | null {
  const baseUri = useStore((s) => s.uri);
  const [src, setSrc] = useState<string | null>(() => immediate(href));

  useEffect(() => {
    let alive = true;
    setSrc(immediate(href));
    resolver.resolveImage(href, baseUri).then((u) => { if (alive) setSrc(u); });
    return () => { alive = false; };
  }, [href, baseUri]);

  return src;
}
