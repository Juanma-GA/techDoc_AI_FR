import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Select, Spinner } from "@internal/ui";

import { ConfirmButton } from "../components/ConfirmButton";
import {
  useCreateProfile,
  useDeleteProfile,
  useProfiles,
  useSetDefaultProfile,
  useUpdateProfile,
} from "../hooks/useProfiles";
import { useTemplates } from "../hooks/useTemplates";
import type { ProfileDto, ProfileInput } from "../lib/api";

// Champs de detection PDF (colonne du tableau PDF).
const PDF_FIELDS = ["fig", "designation", "symbole", "code", "reference", "qty"] as const;
// Champs d'article + colonnes cibles du template Catalogue.
const ITEM_FIELDS = [
  "fig", "figreflink", "aplomb", "description", "matiere",
  "ref_client", "ref_interne", "ref_fournisseur", "qty", "symbole",
] as const;
const CATALOGUE_COLUMNS = [
  "module", "partid", "fig", "figreflink", "aplomb", "description", "matiere", "reperecircuit",
  "modulereference", "bt001_part_no", "sncf_partno", "pn_supplier", "otan_supplier", "qty_assy",
  "app_nom", "app_from", "app_to", "symbole_sncf", "code_pbs", "drw", "nposte",
] as const;

type Draft = { id?: string; name: string; template_id: string; pdf_map: Record<string, number>; excel_map: Record<string, string> };

const EMPTY: Draft = { name: "", template_id: "", pdf_map: {}, excel_map: {} };

function toDraft(p: ProfileDto): Draft {
  return { id: p.id, name: p.name, template_id: p.template_id ?? "", pdf_map: { ...p.pdf_map }, excel_map: { ...p.excel_map } };
}

function toInput(d: Draft): ProfileInput {
  return {
    name: d.name,
    template_id: d.template_id || null,
    pdf_map: d.pdf_map,
    excel_map: d.excel_map,
  };
}

export function Profiles() {
  const { t } = useTranslation();
  const { data: profiles, isLoading } = useProfiles();
  const { data: templates } = useTemplates();
  const create = useCreateProfile();
  const update = useUpdateProfile();
  const setDefault = useSetDefaultProfile();
  const del = useDeleteProfile();

  const [draft, setDraft] = useState<Draft>(EMPTY);

  const save = () => {
    if (!draft.name.trim()) return;
    if (draft.id) update.mutate({ id: draft.id, body: toInput(draft) });
    else create.mutate(toInput(draft), { onSuccess: () => setDraft(EMPTY) });
  };

  const setPdf = (field: string, value: string) =>
    setDraft((d) => {
      const pdf_map = { ...d.pdf_map };
      if (value === "") delete pdf_map[field];
      else pdf_map[field] = Number(value);
      return { ...d, pdf_map };
    });

  const setExcel = (field: string, value: string) =>
    setDraft((d) => {
      const excel_map = { ...d.excel_map };
      if (value === "") delete excel_map[field];
      else excel_map[field] = value;
      return { ...d, excel_map };
    });

  const templateOptions = [
    { value: "", label: t("profiles.templateDefault") },
    ...(templates ?? []).map((tpl) => ({ value: tpl.id, label: tpl.name })),
  ];
  const excelColOptions = [
    { value: "", label: t("profiles.excelDefault") },
    ...CATALOGUE_COLUMNS.map((c) => ({ value: c, label: c })),
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("profiles.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-fg-dim">{t("profiles.hint")}</p>
          {isLoading ? (
            <Spinner />
          ) : !profiles || profiles.length === 0 ? (
            <p className="text-sm text-fg-dim">{t("profiles.empty")}</p>
          ) : (
            <ul className="divide-y divide-md">
              {profiles.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="flex items-center gap-2 text-sm text-fg">
                    {p.name}
                    {p.is_default && <Badge variant="success">{t("profiles.default")}</Badge>}
                  </span>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setDraft(toDraft(p))}>
                      {t("common.edit")}
                    </Button>
                    {!p.is_default && (
                      <Button variant="secondary" size="sm" onClick={() => setDefault.mutate(p.id)}>
                        {t("profiles.setDefault")}
                      </Button>
                    )}
                    <ConfirmButton label={t("common.delete")} onConfirm={() => del.mutate(p.id)} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{draft.id ? t("profiles.editTitle") : t("profiles.newTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="label">{t("profiles.name")}</span>
              <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="label">{t("profiles.template")}</span>
              <Select
                options={templateOptions}
                value={draft.template_id}
                onChange={(e) => setDraft({ ...draft, template_id: e.target.value })}
              />
            </label>
          </div>

          <div>
            <p className="label mb-2">{t("profiles.pdfMapTitle")}</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {PDF_FIELDS.map((f) => (
                <label key={f} className="flex flex-col gap-1">
                  <span className="text-sm text-fg-dim">{t(`profiles.pdfField.${f}`)}</span>
                  <Input
                    type="number"
                    min={0}
                    placeholder={t("profiles.auto")}
                    value={draft.pdf_map[f] ?? ""}
                    onChange={(e) => setPdf(f, e.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="label mb-2">{t("profiles.excelMapTitle")}</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {ITEM_FIELDS.map((f) => (
                <label key={f} className="flex items-center gap-2">
                  <span className="w-32 shrink-0 text-sm text-fg-dim">{t(`profiles.itemField.${f}`)}</span>
                  <Select
                    size="sm"
                    options={excelColOptions}
                    value={draft.excel_map[f] ?? ""}
                    onChange={(e) => setExcel(f, e.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button size="sm" onClick={save} disabled={create.isPending || update.isPending}>
              {draft.id ? t("common.save") : t("profiles.createBtn")}
            </Button>
            {draft.id && (
              <Button variant="ghost" size="sm" onClick={() => setDraft(EMPTY)}>
                {t("profiles.newBtn")}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
