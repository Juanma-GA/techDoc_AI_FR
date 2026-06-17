import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Input, Select, Spinner } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiClientError, exportApi, exportUrl } from "../lib/api";
import { useWorkspace } from "../stores/workspace";

export function Export() {
  const { t } = useTranslation();
  const { runId } = useWorkspace();
  const [status, setStatus] = useState("accepted");
  const [filename, setFilename] = useState("plan_lot3");
  const [kind, setKind] = useState<"csv" | "bat" | "sh">("csv");
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => exportApi.save(runId as string, filename.trim(), kind, status),
    onSuccess: (data) => setSaveMsg({ ok: true, text: t("export.saved", { path: data.path }) }),
    onError: (e) =>
      setSaveMsg({ ok: false, text: e instanceof ApiClientError ? e.message : String(e) }),
  });

  if (!runId) {
    return <EmptyState icon={Download} title={t("export.noRun")} description={t("export.noRunDesc")} />;
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("export.title")}</h1>
        <p className="text-fg-dim">{t("export.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("export.downloadTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            <strong>{t("export.dryRunTitle")}</strong> {t("export.dryRunBody")}
          </p>
          <label className="mb-3 flex max-w-xs flex-col gap-1">
            <span className="label">{t("export.statusLabel")}</span>
            <Select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              options={[
                { value: "accepted", label: t("export.statusAccepted") },
                { value: "all", label: t("export.statusAll") },
              ]}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <a href={exportUrl.csv(runId, status)}>
              <Button>{t("export.csv")}</Button>
            </a>
            <a href={exportUrl.script(runId, "bat", status)}>
              <Button variant="secondary">{t("export.scriptBat")}</Button>
            </a>
            <a href={exportUrl.script(runId, "sh", status)}>
              <Button variant="secondary">{t("export.scriptSh")}</Button>
            </a>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("export.saveTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-info/40 bg-info/10 px-3 py-2 text-sm text-fg-dim">
            {t("export.saveNotice")}
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-1 flex-col gap-1">
              <span className="label">{t("export.filename")}</span>
              <Input value={filename} onChange={(e) => setFilename(e.target.value)} placeholder="plan_lot3" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="label">{t("export.format")}</span>
              <Select
                value={kind}
                onChange={(e) => setKind(e.target.value as "csv" | "bat" | "sh")}
                options={[
                  { value: "csv", label: "CSV" },
                  { value: "bat", label: t("export.scriptBat") },
                  { value: "sh", label: t("export.scriptSh") },
                ]}
              />
            </label>
            <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || !filename.trim()}>
              {saveMutation.isPending ? <Spinner size="sm" /> : null}
              <span>{t("export.saveToOutput")}</span>
            </Button>
          </div>
          {saveMsg ? (
            <p className={saveMsg.ok ? "mt-2 text-sm text-success" : "mt-2 text-sm text-danger"}>{saveMsg.text}</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
