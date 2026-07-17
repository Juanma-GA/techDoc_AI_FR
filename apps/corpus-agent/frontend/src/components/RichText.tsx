// RichText : rendu sur de chaines i18n contenant un balisage inline restreint
// (<code>, <strong>, <br>). Remplace dangerouslySetInnerHTML : le contenu est
// parse par une whitelist et rendu via des elements React, donc tout texte hors
// whitelist (ex. <script>, <img onerror>) est echappe par React et neutralise.
// Defense en profondeur si une traduction backend etait alteree.
import type { ReactNode } from "react";

// Tags inline autorises dans les chaines i18n de confiance. Tout le reste est
// rendu comme texte litteral (echappe par React).
const PAIR_RE = /<(code|strong)>([\s\S]*?)<\/\1>|<br\s*\/?>/gi;

/** Parse une chaine i18n a balisage restreint en noeuds React surs. */
export function renderRichText(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  PAIR_RE.lastIndex = 0;
  while ((m = PAIR_RE.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] === undefined) {
      // <br> : pas de groupe de capture de tag
      nodes.push(<br key={key++} />);
    } else if (m[1].toLowerCase() === "code") {
      nodes.push(<code key={key++}>{m[2]}</code>);
    } else {
      nodes.push(<strong key={key++}>{m[2]}</strong>);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** Composant de commodite : rend une chaine i18n a balisage restreint.
 * Retourne un fragment (sans wrapper) pour preserver le DOM du caller. */
export function RichText({ text }: { text: string }) {
  return <>{renderRichText(text)}</>;
}
