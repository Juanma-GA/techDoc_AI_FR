import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { z } from "zod";
import {
  Badge,
  Button,
  buttonVariants,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  EmptyState,
  Input,
  Spinner,
} from "@internal/ui";

import { ConfirmButton } from "../components/ConfirmButton";
import { useChallenge, useDocument, useReextract, useSaveHeaderMeta } from "../hooks/useDocuments";
import { useCreateItem, useDeleteItem, useItems, usePatchItem } from "../hooks/useItems";
import { downloadExport, type ChallengeRow, type ItemDto } from "../lib/api";
import { useCatiStore } from "../stores/useCatiStore";

const VERDICT_STYLE: Record<string, string> = {
  warning: "border-l-2 border-l-warning",
  extra: "border-l-2 border-l-danger",
  ok: "",
};

const metaSchema = z.object({
  module: z.string(),
  otan_supplier: z.string(),
  drw: z.string(),
  top_assembly: z.string(),
  bom_title: z.string(),
});
type MetaForm = z.infer<typeof metaSchema>;

// Colonnes editables du tableau (cle logique -> largeur).
const COLUMNS: Array<{ key: string; w: string }> = [
  { key: "fig", w: "w-16" },
  { key: "aplomb", w: "w-14" },
  { key: "description", w: "min-w-56" },
  { key: "matiere", w: "w-24" },
  { key: "ref_client", w: "w-24" },
  { key: "ref_interne", w: "w-24" },
  { key: "ref_fournisseur", w: "w-24" },
  { key: "qty", w: "w-20" },
  { key: "symbole", w: "w-20" },
];

function EditableCell({
  value,
  onCommit,
  highlight,
}: {
  value: string;
  onCommit: (v: string) => void;
  highlight?: boolean;
}) {
  return (
    <Input
      defaultValue={value}
      className={`h-8 ${highlight ? "border-warning" : ""}`}
      onBlur={(e) => {
        if (e.target.value !== value) onCommit(e.target.value);
      }}
    />
  );
}

function ItemRow({ docId, item, challenge }: { docId: string; item: ItemDto; challenge?: ChallengeRow }) {
  const { t } = useTranslation();
  const patch = usePatchItem(docId);
  const del = useDeleteItem(docId);

  const rowStyle = challenge ? (VERDICT_STYLE[challenge.verdict] ?? "") : "";
  const issueFields = new Set((challenge?.issues ?? []).map((i) => i.field));

  return (
    <tr className={`border-b border-md ${rowStyle}`}>
      <td className="px-1 py-1 text-center">
        <Checkbox
          checked={item.included}
          onCheckedChange={(c) => patch.mutate({ itemId: item.id, included: !!c })}
        />
      </td>
      {COLUMNS.map((col) => (
        <td key={col.key} className={`px-1 py-1 ${col.w}`}>
          <EditableCell
            value={String(item.fields[col.key] ?? "")}
            highlight={issueFields.has(col.key)}
            onCommit={(v) => patch.mutate({ itemId: item.id, fields: { [col.key]: v } })}
          />
        </td>
      ))}
      <td className="px-1 py-1 text-center">
        {challenge?.verdict === "warning" && (
          <Badge
            variant="warning"
            title={challenge.issues
              .map((i) => `${i.field}: ${i.deterministic} ≠ ${i.llm}`)
              .join("\n")}
          >
            {t("table.challenge.mismatch")}
          </Badge>
        )}
        {challenge?.verdict === "extra" && <Badge variant="danger">{t("table.challenge.extra")}</Badge>}
        {!challenge && item.edited && <Badge variant="warning">{t("table.edited")}</Badge>}
      </td>
      <td className="px-1 py-1">
        <ConfirmButton label={t("common.delete")} onConfirm={() => del.mutate(item.id)} />
      </td>
    </tr>
  );
}

export function Table() {
  const { t } = useTranslation();
  const docId = useCatiStore((s) => s.selectedDocId);
  const { data: doc } = useDocument(docId);
  const { data: itemsData, isLoading } = useItems(docId);
  const saveMeta = useSaveHeaderMeta(docId ?? "");
  const reextract = useReextract(docId ?? "");
  const createItem = useCreateItem(docId ?? "");
  const challenge = useChallenge(docId ?? "");

  const report = doc?.challenge;
  const verdictByFig = useMemo(() => {
    const map = new Map<string, ChallengeRow>();
    (report?.rows ?? []).forEach((r) => {
      if (r.verdict !== "missing") map.set(r.fig.toUpperCase(), r);
    });
    return map;
  }, [report]);
  const missingRows = (report?.rows ?? []).filter((r) => r.verdict === "missing");

  const { register, handleSubmit, reset } = useForm<MetaForm>({
    resolver: zodResolver(metaSchema),
    defaultValues: { module: "", otan_supplier: "", drw: "", top_assembly: "", bom_title: "" },
  });

  useEffect(() => {
    if (doc?.header_meta) reset(doc.header_meta);
  }, [doc?.header_meta, reset]);

  if (!docId) {
    return (
      <div className="mx-auto max-w-xl">
        <EmptyState title={t("table.noDocTitle")} description={t("table.noDocDescription")} />
        <div className="mt-4 text-center">
          <Link to="/import" className={buttonVariants({ variant: "primary" })}>
            {t("nav.import")}
          </Link>
        </div>
      </div>
    );
  }

  const onExport = () => {
    const base = doc?.header_meta.module?.trim() || "nomenclature";
    void downloadExport(docId, `${base}.xlsx`);
  };

  const META_FIELDS: Array<keyof MetaForm> = ["module", "bom_title", "otan_supplier", "top_assembly", "drw"];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("table.metaTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid grid-cols-2 gap-3 md:grid-cols-3"
            onSubmit={handleSubmit((v) => saveMeta.mutate(v))}
          >
            {META_FIELDS.map((f) => (
              <label key={f} className="flex flex-col gap-1">
                <span className="label">{t(`table.meta.${f}`)}</span>
                <Input {...register(f)} />
              </label>
            ))}
            <div className="col-span-full flex items-center gap-2">
              <Button type="submit" size="sm" disabled={saveMeta.isPending}>
                {t("table.saveMeta")}
              </Button>
              {saveMeta.isSuccess && <span className="text-sm text-success">{t("common.saved")}</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{t("table.itemsTitle")}</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => reextract.mutate()} disabled={reextract.isPending}>
                {t("table.reextract")}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => challenge.mutate()}
                disabled={challenge.isPending}
              >
                {challenge.isPending ? t("table.challenge.running") : t("table.challenge.verify")}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => createItem.mutate({})}>
                {t("table.addRow")}
              </Button>
              <Button size="sm" onClick={onExport}>
                {t("table.export")}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {itemsData && itemsData.warnings.length > 0 && (
            <p className="mb-2 text-sm text-warning">{itemsData.warnings.join(" · ")}</p>
          )}

          {report && report.status === "skipped" && (
            <p className="mb-2 text-sm text-fg-dim">{t("table.challenge.skipped")}</p>
          )}
          {report && report.status === "done" && (
            <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              {report.summary.clean ? (
                <Badge variant="success">{t("table.challenge.clean")}</Badge>
              ) : (
                <>
                  {report.summary.warning > 0 && (
                    <Badge variant="warning">
                      {t("table.challenge.warnings", { count: report.summary.warning })}
                    </Badge>
                  )}
                  {report.summary.extra > 0 && (
                    <Badge variant="danger">{t("table.challenge.extras", { count: report.summary.extra })}</Badge>
                  )}
                  {report.summary.missing > 0 && (
                    <Badge variant="info">{t("table.challenge.missings", { count: report.summary.missing })}</Badge>
                  )}
                </>
              )}
            </div>
          )}
          {missingRows.length > 0 && (
            <div className="mb-3 rounded-sm border border-info/40 bg-info/10 p-2 text-sm">
              <p className="mb-1 font-medium text-info">{t("table.challenge.missingTitle")}</p>
              <ul className="list-disc pl-5 text-fg-dim">
                {missingRows.map((r) => (
                  <li key={r.fig}>
                    {r.fig} — {r.llm_only?.description ?? ""} ({r.llm_only?.ref_interne ?? ""})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {isLoading ? (
            <Spinner />
          ) : !itemsData || itemsData.items.length === 0 ? (
            <EmptyState title={t("table.emptyTitle")} description={t("table.emptyDescription")} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-md text-left">
                    <th className="px-1 py-2" />
                    {COLUMNS.map((c) => (
                      <th key={c.key} className="px-1 py-2 label">
                        {t(`table.col.${c.key}`)}
                      </th>
                    ))}
                    <th className="px-1 py-2" />
                    <th className="px-1 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {itemsData.items.map((item) => (
                    <ItemRow
                      key={item.id}
                      docId={docId}
                      item={item}
                      challenge={verdictByFig.get(String(item.fields.fig ?? "").toUpperCase())}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
