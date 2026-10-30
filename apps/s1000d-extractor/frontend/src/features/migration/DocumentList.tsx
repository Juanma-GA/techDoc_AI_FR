import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Select, Spinner } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { documentsApi } from "../../lib/api";
import type { MigrationInputs } from "./useMigrationInputs";
import type { MigrationWizard } from "./useMigrationWizard";
import { ConfirmAction } from "./ConfirmAction";

const variants = {
  extracted: "success", incomplete: "danger", extract_failed: "danger", wizard: "info", uploaded: "default",
} as const;
export function DocumentList({ inputs, wizard }: { inputs: MigrationInputs; wizard: MigrationWizard }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("recent");
  const query = useQuery({
    queryKey: ["s1000d-docs", inputs.mode], queryFn: documentsApi.list,
    enabled: inputs.ready && !inputs.loading,
  });
  const docs = (query.data ?? []).filter((doc) =>
    doc.filename.toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => {
      if (sort === "name") return a.filename.localeCompare(b.filename);
      return (sort === "recent" ? -1 : 1) * (a.created_at ?? "").localeCompare(b.created_at ?? "");
    });
  return <Card>
    <CardHeader><CardTitle>{t("migration.docs.title")}</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <Input aria-label={t("migration.ui.search")} placeholder={t("migration.ui.search")}
          value={search} onChange={(event) => setSearch(event.target.value)} />
        <Select aria-label={t("migration.ui.sort")} value={sort} onChange={(event) => setSort(event.target.value)}
          options={["recent", "oldest", "name"].map((value) => ({ value, label: t(`migration.ui.sort_${value}`) }))} />
      </div>
      {query.error ? <p role="alert" className="text-danger">{query.error.message}</p> : null}
      {query.isLoading ? <Spinner aria-label={t("common.loading")} /> : null}
      {docs.length ? docs.map((doc) => <div key={doc.id}
        className="flex flex-wrap items-center justify-between gap-3 border-b border-md py-3 [content-visibility:auto]">
        <div className="min-w-0">
          <p className="break-all">{doc.filename} <Badge variant={
            doc.status in variants ? variants[doc.status as keyof typeof variants] : "warning"
          }>{t(`docStatus.${doc.status}`, { defaultValue: doc.status })}</Badge></p>
          <span className="text-sm text-fg-dim">{doc.source_format.toUpperCase()}</span>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="secondary" size="sm" disabled={wizard.busy}
            onClick={() => void wizard.open(doc.id)}>{t("migration.docs.open")}</Button>
          <ConfirmAction label={t("migration.docs.delete")} disabled={wizard.busy}
            onConfirm={() => void wizard.remove(doc.id)} />
        </div>
      </div>) : !query.isLoading && !query.error ? <p className="text-fg-dim">{t("migration.docs.empty")}</p> : null}
    </CardContent>
  </Card>;
}
