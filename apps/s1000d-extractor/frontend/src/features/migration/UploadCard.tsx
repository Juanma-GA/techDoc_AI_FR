import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, SelectMenu } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { BrexProfileControl } from "../../components/BrexProfileControl";
import type { MigrationInputs } from "./useMigrationInputs";
import type { MigrationWizard } from "./useMigrationWizard";
import { ResourceField } from "./ResourceField";
import { StartProgress } from "./StartProgress";

export function UploadCard({ inputs, wizard }: { inputs: MigrationInputs; wizard: MigrationWizard }) {
  const { t } = useTranslation();
  const [brexReady, setBrexReady] = useState(true);
  const savedName = inputs.mapping?.files.document?.filename;
  const schema = useMemo(() => z.object({
    source: z.instanceof(File).nullable()
      .refine((file) => file !== null || !!savedName, t("migration.upload.noFile"))
      .refine((file) => !file || (file.size > 0 && /\.(pdf|docx)$/i.test(file.name)), t("migration.ui.invalidFile")),
    issue: z.enum(["4.1", "4.2"]),
  }), [savedName, t]);
  const { control, handleSubmit, reset, formState } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema), defaultValues: { source: inputs.file, issue: inputs.issue },
  });
  useEffect(() => reset({ source: inputs.file, issue: inputs.issue }), [inputs.file, inputs.issue, reset]);
  const disabled = inputs.loading || wizard.busy || !!wizard.starting || !!wizard.pdfCut ||
    wizard.pdfCutBusy || formState.isSubmitting;
  return <Card>
    <CardHeader><CardTitle>{t("migration.upload.title")}</CardTitle></CardHeader>
    <CardContent>
      <form className="space-y-4" onSubmit={handleSubmit(wizard.start)} noValidate>
        <Controller control={control} name="source" render={({ field }) =>
          <ResourceField label={t("migration.upload.file")} accept=".pdf,.docx" disabled={disabled}
            onSelect={(file) => {
              field.onChange(file);
              field.onBlur();
              inputs.selectDocument(file);
            }}
            status={<>
              {inputs.file || savedName ? <span className="block text-sm text-fg-dim" role="status">
                {t(inputs.file ? "migration.upload.selectedFile" : "migration.upload.lastDocument",
                  { filename: inputs.file?.name ?? savedName })}
              </span> : null}
              {formState.errors.source ? <span role="alert" className="text-sm text-danger">
                {formState.errors.source.message}
              </span> : null}
            </>} />} />
        <label className="block space-y-2">
          <span>{t("migration.upload.issue")}</span>
          <Controller control={control} name="issue" render={({ field }) =>
            <SelectMenu
              id={field.name}
              name={field.name}
              ref={field.ref}
              label={t("migration.upload.issue")}
              value={field.value}
              onBlur={field.onBlur}
              disabled={disabled}
              options={["4.2", "4.1"].map((issue) => ({
                value: issue, label: t("migration.upload.issueValue", { issue }),
              }))}
              onValueChange={(issue) => {
                field.onChange(issue);
                if (issue === "4.1" || issue === "4.2") {
                  inputs.setIssue(issue);
                }
              }}
            />
          } />
          {formState.errors.issue ? <span role="alert" className="text-danger">
            {t("migration.ui.invalidIssue")}
          </span> : null}
        </label>
        {inputs.mode === "demo" ? null : <BrexProfileControl issue={inputs.issue}
          value={inputs.brexId} onChange={inputs.setBrexId} onReadyChange={setBrexReady} disabled={disabled} />}
        <fieldset className="space-y-3 border-t pt-4">
          <legend className="pr-2 font-mono text-label uppercase text-fg-dim">
            {t("migration.upload.resourcesTitle")}
          </legend>
          <div className="grid items-start gap-4 md:grid-cols-3">
            {(["dmrl", "dm_header"] as const).map((kind) => {
              const name = inputs.resources[kind]?.name ?? inputs.mapping?.files[kind]?.filename;
              const dmrl = kind === "dmrl";
              return <ResourceField key={kind} disabled={disabled} filename={name}
                label={t(dmrl ? "migration.upload.dmrl" : "migration.upload.dmHeader")}
                hint={t(dmrl ? "migration.upload.dmrlHint" : "migration.upload.dmHeaderHint")}
                help={dmrl ? undefined : t("migration.upload.dmHeaderHelp")}
                accept={dmrl ? ".xlsx,.xlsm,.csv,.json" : ".json,.xml"}
                onSelect={(file) => inputs.selectResource(kind, file)}
                onClear={() => inputs.selectResource(kind, null)} />;
            })}
            <ResourceField label={t("migration.upload.cir")} hint={t("migration.upload.cirHint")}
              accept=".xml" disabled onSelect={() => undefined}
              status={<Badge className="self-start">{t("migration.upload.inDevelopment")}</Badge>} />
          </div>
        </fieldset>
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={disabled || !brexReady}>{t("migration.upload.start")}</Button>
          <StartProgress progress={wizard.starting} />
          {inputs.loading ? <span role="status">
            {t(inputs.mode === "demo" ? "demo.filesLoading" : "common.loading")}
          </span> : null}
          {inputs.error ? <span role="alert" className="text-danger">{inputs.error}</span> : null}
        </div>
      </form>
    </CardContent>
  </Card>;
}
