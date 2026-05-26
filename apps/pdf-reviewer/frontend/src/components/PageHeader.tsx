import type { ReactNode } from "react";

type Props = { title: string; subtitle?: string; actions?: ReactNode };

export function PageHeader({ title, subtitle, actions }: Props) {
  return (
    <header className="flex items-center justify-between border-b px-6 py-4">
      <div>
        <h1 className="font-display text-xl text-fg">{title}</h1>
        {subtitle ? <p className="text-fg-dim">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}
