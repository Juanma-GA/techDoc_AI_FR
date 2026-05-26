type Props = {
  title: string;
  subtitle?: string;
};

export function PageHeader({ title, subtitle }: Props) {
  return (
    <header className="mb-6">
      <h1 className="font-display text-2xl text-fg">{title}</h1>
      {subtitle ? <p className="mt-1 text-fg-dim">{subtitle}</p> : null}
    </header>
  );
}
