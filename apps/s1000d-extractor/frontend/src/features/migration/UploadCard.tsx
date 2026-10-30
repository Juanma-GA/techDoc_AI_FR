import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Select } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { CircleHelp } from "lucide-react";
import { BrexProfileControl } from "../../components/BrexProfileControl";
import type { MigrationInputs } from "./useMigrationInputs";
import type { MigrationWizard } from "./useMigrationWizard";
import { ConfirmAction } from "./ConfirmAction";
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
        <label className="block space-y-2">
          <span>{t("migration.upload.file")}</span>
          <Controller control={control} name="source" render={({ field }) =>
            <Input type="file" accept=".pdf,.docx" disabled={disabled} ref={field.ref}
              onBlur={field.onBlur} aria-invalid={!!formState.errors.source}
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                field.onChange(file);
                inputs.selectDocument(file);
              }} />} />
          {inputs.file || savedName ? <span className="block text-sm text-fg-dim" role="status">
            {t(inputs.file ? "migration.upload.selectedFile" : "migration.upload.lastDocument",
              { filename: inputs.file?.name ?? savedName })}
          </span> : null}
          {formState.errors.source ? <span role="alert" className="text-danger">
            {formState.errors.source.message}
          </span> : null}
        </label>
        <label className="block space-y-2">
          <span>{t("migration.upload.issue")}</span>
          <Controller control={control} name="issue" render={({ field }) =>
            <Select {...field} aria-label={t("migration.upload.issue")} disabled={disabled} options={["4.2", "4.1"].map((issue) => ({
              value: issue, label: t("migration.upload.issueValue", { issue }),
            }))} onChange={(event) => {
              field.onChange(event.target.value);
              if (event.target.value === "4.1" || event.target.value === "4.2") {
                inputs.setIssue(event.target.value);
              }
            }} />} />
          {formState.errors.issue ? <span role="alert" className="text-danger">
            {t("migration.ui.invalidIssue")}
          </span> : null}
        </label>
        {inputs.mode === "demo" ? null : <BrexProfileControl issue={inputs.issue}
          value={inputs.brexId} onChange={inputs.setBrexId} onReadyChange={setBrexReady} disabled={disabled} />}
        <div className="grid gap-4 md:grid-cols-3">
          {(["dmrl", "dm_header"] as const).map((kind) => {
            const name = inputs.resources[kind]?.name ?? inputs.mapping?.files[kind]?.filename;
            return <div key={kind} className="space-y-2">
              <label className="block space-y-2">
                <span>{t(kind === "dmrl" ? "migration.upload.dmrl" : "migration.upload.dmHeader")}</span>
                <Input type="file" accept={kind === "dmrl" ? ".xlsx,.xlsm,.csv,.json" : ".json,.xml"}
                  disabled={disabled} onChange={(event) => inputs.selectResource(kind, event.target.files?.[0] ?? null)} />
              </label>
              {kind === "dm_header" ? <Button type="button" variant="ghost" size="sm"
                title={t("migration.upload.dmHeaderHelp")} aria-label={t("migration.upload.dmHeaderHelp")}>
                <CircleHelp size={15} aria-hidden="true" />
              </Button> : null}
              {name ? <><p className="break-all text-sm text-fg-dim" role="status">
                {t("migration.upload.selectedFile", { filename: name })}
              </p><ConfirmAction label={t("migration.ui.clearResource")} disabled={disabled}
                onConfirm={() => inputs.selectResource(kind, null)} /></> : null}
            </div>;
          })}
          <label className="space-y-2">
            <span>{t("migration.upload.cir")}</span>
            <Input type="file" accept=".xml" disabled aria-describedby="conversion-cir-status" />
            <span id="conversion-cir-status" className="text-sm text-fg-dim">{t("migration.upload.inDevelopment")}</span>
          </label>
        </div>
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
