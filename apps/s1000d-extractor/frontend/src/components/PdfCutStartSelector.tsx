import { useEffect, useMemo } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, SelectMenu } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { pdfCutApi, type PdfCutDetection } from "../lib/api";

type PdfCutStartSelectorProps = {
  docId: string;
  detection: PdfCutDetection;
  selectedTitle: string;
  startPage: number | null;
  endPage: number | null;
  busy: boolean;
  onTitleChange: (title: string) => void;
  onDetect: (title: string) => void;
  onStartPageChange: (page: number | null) => void;
  onEndPageChange: (page: number | null) => void;
  onConfirm: () => void;
};

export function PdfCutStartSelector({
  docId,
  detection,
  selectedTitle,
  startPage,
  endPage,
  busy,
  onTitleChange,
  onDetect,
  onStartPageChange,
  onEndPageChange,
  onConfirm,
}: PdfCutStartSelectorProps) {
  const { t } = useTranslation();
  const schema = useMemo(() => {
    const page = z.string()
      .regex(/^[1-9]\d*$/, t("migration.upload.pdfCut.invalidPage"))
      .refine(
        (value) => Number(value) <= detection.total_pages,
        t("migration.upload.pdfCut.pageTooLarge", { total: detection.total_pages }),
      );
    return z.object({
      startPage: page,
      endPage: page,
    }).superRefine(({ startPage: start, endPage: end }, context) => {
      if (Number(start) > Number(end)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["endPage"],
          message: t("migration.upload.pdfCut.invalidRange"),
        });
      }
    });
  }, [detection.total_pages, t]);
  const { control, handleSubmit, reset, formState } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      startPage: startPage == null ? "" : String(startPage),
      endPage: endPage == null ? "" : String(endPage),
    },
    mode: "onChange",
  });

  useEffect(() => {
    reset({
      startPage: startPage == null ? "" : String(startPage),
      endPage: endPage == null ? "" : String(endPage),
    });
  }, [startPage, endPage, reset]);

  return (
    <Card>
      <CardHeader><CardTitle>{t("migration.upload.pdfCut.title")}</CardTitle></CardHeader>
      <CardContent>
        <form className="space-y-4" noValidate onSubmit={handleSubmit(() => onConfirm())}>
          <p className="text-sm text-fg-dim">{t("migration.upload.pdfCut.help")}</p>
          {detection.dmrl_titles.length ? (
            <div className="flex flex-wrap items-end gap-3">
              <label className="min-w-0 flex-1 space-y-2">
                <span className="block text-label font-mono uppercase text-fg-dim">
                  {t("migration.upload.pdfCut.firstDmTitle")}
                </span>
                <SelectMenu
                  label={t("migration.upload.pdfCut.firstDmTitle")}
                  value={selectedTitle}
                  disabled={busy}
                  onValueChange={onTitleChange}
                  options={detection.dmrl_titles.map((title) => ({ value: title, label: title }))}
                />
              </label>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || !selectedTitle}
                onClick={() => onDetect(selectedTitle)}
              >
                {busy
                  ? t("migration.upload.pdfCut.searching")
                  : t("migration.upload.pdfCut.detectWithTitle")}
              </Button>
            </div>
          ) : null}
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-2">
              <span className="block text-label font-mono uppercase text-fg-dim">
                {t("migration.upload.pdfCut.startPage")}
              </span>
              <Controller control={control} name="startPage" render={({ field }) =>
                <Input
                  {...field}
                  type="number"
                  min={1}
                  max={detection.total_pages}
                  disabled={busy}
                  onChange={(event) => {
                    field.onChange(event.target.value);
                    onStartPageChange(Number(event.target.value) || null);
                  }}
                />
              } />
              {formState.errors.startPage ? <span role="alert" className="block text-sm text-danger">
                {formState.errors.startPage.message}
              </span> : null}
            </label>
            <label className="space-y-2">
              <span className="block text-label font-mono uppercase text-fg-dim">
                {t("migration.upload.pdfCut.endPage")}
              </span>
              <Controller control={control} name="endPage" render={({ field }) =>
                <Input
                  {...field}
                  type="number"
                  min={1}
                  max={detection.total_pages}
                  disabled={busy}
                  onChange={(event) => {
                    field.onChange(event.target.value);
                    onEndPageChange(Number(event.target.value) || null);
                  }}
                />
              } />
              {formState.errors.endPage ? <span role="alert" className="block text-sm text-danger">
                {formState.errors.endPage.message}
              </span> : null}
            </label>
            <Button type="submit" disabled={busy}>
              {t("migration.upload.pdfCut.validate")}
            </Button>
          </div>
          {startPage != null ? (
            <img
              className="mt-4 block max-h-[35rem] max-w-full border border-md object-contain"
              src={pdfCutApi.previewUrl(docId, startPage)}
              alt={t("migration.upload.pdfCut.previewAlt", { page: startPage })}
            />
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
