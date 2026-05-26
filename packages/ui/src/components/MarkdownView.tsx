import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "../lib/utils";

export type MarkdownViewProps = {
  content: string;
  className?: string;
};

/**
 * Rendu markdown via react-markdown + remark-gfm. La typographie est
 * appliquée par des classes Tailwind utilisant les tokens (pas de hex).
 */
export function MarkdownView({ content, className }: MarkdownViewProps) {
  return (
    <div
      className={cn(
        "prose-like text-fg",
        "[&_h1]:font-display [&_h1]:text-xl [&_h1]:text-fg [&_h1]:mt-4 [&_h1]:mb-2",
        "[&_h2]:font-display [&_h2]:text-lg [&_h2]:text-fg [&_h2]:mt-3 [&_h2]:mb-2",
        "[&_h3]:font-display [&_h3]:text-base [&_h3]:text-fg [&_h3]:mt-3 [&_h3]:mb-1",
        "[&_p]:my-2 [&_p]:leading-relaxed",
        "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5",
        "[&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5",
        "[&_li]:my-0.5",
        "[&_a]:text-brand-blue-light [&_a]:underline",
        "[&_code]:rounded-sm [&_code]:bg-bg-3 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-sm",
        "[&_pre]:my-3 [&_pre]:overflow-auto [&_pre]:rounded-sm [&_pre]:bg-bg-3 [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-sm",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        "[&_blockquote]:my-2 [&_blockquote]:border-l-2 [&_blockquote]:border-md [&_blockquote]:pl-3 [&_blockquote]:text-fg-dim",
        "[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-sm",
        "[&_th]:border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-fg",
        "[&_td]:border [&_td]:px-2 [&_td]:py-1 [&_td]:text-fg",
        "[&_hr]:my-4 [&_hr]:border-md",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
