import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, KpiCard, Select } from "@internal/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { GitCompare } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { diffApi, exportUrl, importsApi, type DiffEntryDto, type DiffRunDto, type ImportDto } from "../lib/api";

const CHANGE_VARIANT: Record<string, "success" | "danger" | "warning"> = {
  added: "success",
  removed: "danger",
  modified: "warning",
};

export function Diff() {
  const { t } = useTranslation();
  const importsQuery = useQuery<ImportDto[]>({ queryKey: ["imports"], queryFn: importsApi.list });
  const imports = importsQuery.data ?? [];
  const [base, setBase] = useState("");
  const [other, setOther] = useState("");
  const [run, setRun] = useState<DiffRunDto | null>(null);
  const [entries, setEntries] = useState<DiffEntryDto[]>([]);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await diffApi.create(base || imports[0]?.id, other || imports[1]?.id);
      const e = await diffApi.entries(r.id);
      return { r, e };
    },
    onSuccess: ({ r, e }) => {
      setRun(r);
      setEntries(e);
    },
  });

  if (imports.length < 2) {
    return <EmptyState icon={GitCompare} title={t("diff.needTwo")} description={t("diff.needTwoDesc")} />;
  }

  const opts = imports.map((i) => ({ value: i.id, label: `${i.root_label} (${i.node_count})` }));

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("diff.title")}</h1>
        <p className="text-fg-dim">{t("diff.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("diff.compareTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-1 flex-col gap-1">
              <span className="label">{t("diff.base")}</span>
              <Select options={opts} value={base || opts[0].value} onChange={(e) => setBase(e.target.value)} />
            </label>
            <label className="flex flex-1 flex-col gap-1">
              <span className="label">{t("diff.other")}</span>
              <Select options={opts} value={other || opts[1].value} onChange={(e) => setOther(e.target.value)} />
            </label>
            <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {t("diff.compare")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {run ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("diff.resultTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 grid grid-cols-3 gap-3">
              <KpiCard label={t("diff.added")} value={run.summary.added ?? 0} />
              <KpiCard label={t("diff.removed")} value={run.summary.removed ?? 0} />
              <KpiCard label={t("diff.modified")} value={run.summary.modified ?? 0} />
            </div>
            <a href={exportUrl.diffCsv(run.id)} className="mb-3 inline-block">
              <Button variant="secondary" size="sm">{t("common.exportCsv")}</Button>
            </a>
            <ul className="flex flex-col gap-1">
              {entries.map((e) => (
                <li key={e.id} className="flex items-center gap-2 rounded-sm bg-bg-2 px-3 py-1.5 font-mono text-sm">
                  <Badge variant={CHANGE_VARIANT[e.change_type]}>{e.change_type}</Badge>
                  <span className="break-all">{e.rel_path}</span>
                  {e.detail ? <span className="text-fg-dim">— {e.detail}</span> : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
