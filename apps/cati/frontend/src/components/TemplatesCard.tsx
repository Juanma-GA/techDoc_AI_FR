import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, FileDropzone, Spinner } from "@internal/ui";

import { useDeleteTemplate, useSetDefaultTemplate, useTemplates, useUploadTemplate } from "../hooks/useTemplates";
import { ConfirmButton } from "./ConfirmButton";

export function TemplatesCard() {
  const { t } = useTranslation();
  const { data: templates, isLoading } = useTemplates();
  const upload = useUploadTemplate();
  const setDefault = useSetDefaultTemplate();
  const del = useDeleteTemplate();
  const [name, setName] = useState("");

  const onFiles = (files: File[]) => {
    const file = files[0];
    if (!file) return;
    upload.mutate({ file, name: name.trim() || file.name });
    setName("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("templates.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-fg-dim">{t("templates.hint")}</p>

        <input
          className="block w-full rounded-sm border border-md bg-bg-2 px-3 py-2 text-sm text-fg"
          placeholder={t("templates.namePlaceholder")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <FileDropzone
          accept=".xlsx"
          multiple={false}
          onFiles={onFiles}
          disabled={upload.isPending}
          label={t("templates.dropLabel")}
          description={t("templates.dropDescription")}
        />
        {upload.isError && <p className="text-sm text-danger">{t("templates.uploadError")}</p>}

        {isLoading ? (
          <Spinner />
        ) : !templates || templates.length === 0 ? (
          <p className="text-sm text-fg-dim">{t("templates.empty")}</p>
        ) : (
          <ul className="divide-y divide-md">
            {templates.map((tpl) => (
              <li key={tpl.id} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 truncate text-sm text-fg">
                    {tpl.name}
                    {tpl.is_default && <Badge variant="success">{t("templates.default")}</Badge>}
                  </p>
                  <p className="text-label text-fg-dim">
                    {tpl.sheet_name} · {tpl.header_columns.length} {t("templates.columns")}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {!tpl.is_default && (
                    <Button variant="secondary" size="sm" onClick={() => setDefault.mutate(tpl.id)}>
                      {t("templates.setDefault")}
                    </Button>
                  )}
                  <ConfirmButton label={t("common.delete")} onConfirm={() => del.mutate(tpl.id)} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
