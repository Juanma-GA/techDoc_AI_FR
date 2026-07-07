import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
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
import { useDocument, useReextract, useSaveHeaderMeta } from "../hooks/useDocuments";
import { useCreateItem, useDeleteItem, useItems, usePatchItem } from "../hooks/useItems";
import { downloadExport, type ItemDto } from "../lib/api";
import { useCatiStore } from "../stores/useCatiStore";

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
}: {
  value: string;
  onCommit: (v: string) => void;
}) {
  return (
    <Input
      defaultValue={value}
      className="h-8"
      onBlur={(e) => {
        if (e.target.value !== value) onCommit(e.target.value);
      }}
    />
  );
}

function ItemRow({ docId, item }: { docId: string; item: ItemDto }) {
  const { t } = useTranslation();
  const patch = usePatchItem(docId);
  const del = useDeleteItem(docId);

  return (
    <tr className="border-b border-md">
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
            onCommit={(v) => patch.mutate({ itemId: item.id, fields: { [col.key]: v } })}
          />
        </td>
      ))}
      <td className="px-1 py-1 text-center">
        {item.edited && <Badge variant="warning">{t("table.edited")}</Badge>}
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
                    <ItemRow key={item.id} docId={docId} item={item} />
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
