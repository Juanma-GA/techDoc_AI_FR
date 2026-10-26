import { zodResolver } from "@hookform/resolvers/zod";
import { Button, Input } from "@internal/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { errorText } from "../../lib/api";
import { flowsApi } from "../../lib/flowApi";
import { useEditorStore } from "../../stores/editorStore";
import type { FlowGraph } from "../../types/flow";

const schema = z.object({ name: z.string().trim().min(1).max(200) });
type Values = z.infer<typeof schema>;

export function SavePanel({ graph }: { graph: FlowGraph }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { name, sourceType, source, currentFlowId, setSaved } = useEditorStore();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name } });

  useEffect(() => form.reset({ name }), [name, form]);

  const save = useMutation({
    mutationFn: (values: Values) => {
      const body = { name: values.name, source_type: sourceType, source_text: source, graph };
      return currentFlowId ? flowsApi.update(currentFlowId, body) : flowsApi.create(body);
    },
    onSuccess: (flow) => {
      setSaved(flow.id, flow.name);
      void qc.invalidateQueries({ queryKey: ["flows"] });
      void qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  const error = form.formState.errors.name;
  return (
    <form className="flex flex-col gap-2" onSubmit={form.handleSubmit((v) => save.mutate(v))}>
      <label htmlFor="flow-name">
        {t("editor.save.name")}
      </label>
      <div className="flex flex-wrap gap-2">
        <Input
          id="flow-name"
          className="min-w-[16rem] flex-1"
          state={error ? "error" : "default"}
          {...form.register("name")}
        />
        <Button type="submit" disabled={save.isPending}>
          {currentFlowId ? t("editor.save.update") : t("editor.save.create")}
        </Button>
      </div>
      {error && <span className="text-danger">{t("editor.save.nameInvalid")}</span>}
      {save.isSuccess && <span className="text-success">{t("editor.save.done")}</span>}
      {save.isError && (
        <span className="text-danger" role="alert">
          {errorText(save.error)}
        </span>
      )}
    </form>
  );
}
