import { Badge, Button, Select, buttonVariants } from "@internal/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Files, FileSpreadsheet, FolderOpen, GitCompareArrows } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  diffApi,
  exportUrl,
  importsApi,
  type DiffEntryDto,
  type DiffRunDto,
  type ImportDto,
} from "../lib/api";
import { NomenclatureDiff } from "../components/business/NomenclatureDiff";
import { CatPartDiff } from "./CatPartDiff";

const CHANGE_VARIANT: Record<string, "success" | "danger" | "warning"> = {
  added: "success",
  removed: "danger",
  modified: "warning",
};

/** Onglet 1 : comparaison de deux dossiers importés (existant). */
function FoldersDiff() {
  const { t } = useTranslation();
  const importsQuery = useQuery<ImportDto[]>({ queryKey: ["imports"], queryFn: importsApi.list });
  const imports = importsQuery.data ?? [];
  const [base, setBase] = useState("");
  const [other, setOther] = useState("");
  const [run, setRun] = useState<DiffRunDto | null>(null);
  const [entries, setEntries] = useState<DiffEntryDto[]>([]);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await diffApi.create(base || imports[0]!.id, other || imports[1]!.id);
      const e = await diffApi.entries(r.id);
      return { r, e };
    },
    onSuccess: ({ r, e }) => {
      setError(null);
      setRun(r);
      setEntries(e);
    },
    onError: (err) => setError(err instanceof ApiClientError ? err.message : String(err)),
  });

  if (imports.length < 2) {
    return (
      <div className="empty-state">
        <h3 className="section-title">{t("diff.needTwo")}</h3>
        <p className="hint">{t("diff.needTwoDesc")}</p>
      </div>
    );
  }

  const opts = imports.map((i) => ({ value: i.id, label: `${i.root_label} (${i.node_count})` }));

  return (
    <div className="form">
      <section className="workflow-section">
        <h2 className="section-title">{t("diff.compareTitle")}</h2>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field grow">
            <span className="field-label">{t("diff.base")}</span>
            <Select options={[]}  value={base || opts[0]!.value} onChange={(e) => setBase(e.target.value)}>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </label>
          <label className="field grow">
            <span className="field-label">{t("diff.other")}</span>
            <Select options={[]}  value={other || opts[1]!.value} onChange={(e) => setOther(e.target.value)}>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </label>
          <Button type="button" variant="primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <GitCompareArrows size={16} aria-hidden="true" />
            {t("diff.compare")}
          </Button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section className="workflow-section">
        {run ? (
          <>
            <h2 className="section-title">{t("diff.resultTitle")}</h2>
            <div className="kpi-grid">
              <div className="kpi">
                <span className="label">{t("diff.added")}</span>
                <span className="kpi-value">{run.summary.added ?? 0}</span>
              </div>
              <div className="kpi">
                <span className="label">{t("diff.removed")}</span>
                <span className="kpi-value">{run.summary.removed ?? 0}</span>
              </div>
              <div className="kpi">
                <span className="label">{t("diff.modified")}</span>
                <span className="kpi-value">{run.summary.modified ?? 0}</span>
              </div>
            </div>
            <a href={exportUrl.diffCsv(run.id)} className={buttonVariants({ variant: "secondary", size: "sm" })}>
              <Download size={16} aria-hidden="true" />
              {t("common.exportCsv")}
            </a>
            {entries.length > 0 ? (
              <ul className="item-list">
                {entries.map((e) => (
                  <li key={e.id} className="item-row">
                    <Badge variant={CHANGE_VARIANT[e.change_type] ?? "default"}>{t(`diff.${e.change_type}`, { defaultValue: e.change_type })}</Badge>
                    <div className="item-main">
                      <span className="item-name">{e.rel_path}</span>
                      {e.detail ? <span className="item-meta">{`— ${e.detail}`}</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <h3 className="section-title">{t("diff.noDifference")}</h3>
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">
            <h3 className="section-title">{t("diff.runPrompt")}</h3>
          </div>
        )}
      </section>
    </div>
  );
}

export function Diff() {
  const { t } = useTranslation();
  // Focus sur la comparaison de nomenclatures (SIN / PN) par defaut.
  const [tab, setTab] = useState<"folders" | "nomenclatures" | "catparts">("nomenclatures");
  const tabs = [
    { key: "folders", label: t("diff.tabFolders"), icon: FolderOpen },
    { key: "nomenclatures", label: t("diff.tabNomenclatures"), icon: FileSpreadsheet },
    { key: "catparts", label: t("catpartDiff.tab"), icon: Files },
  ] as const;

  return (
    <div className="flex flex-col gap-4">
      <div className="row" role="tablist" aria-label={t("nav.diff")} onKeyDown={(event) => {
        const index = tabs.findIndex((item) => item.key === tab);
        const nextIndex = event.key === "ArrowRight" ? (index + 1) % tabs.length
          : event.key === "ArrowLeft" ? (index - 1 + tabs.length) % tabs.length
            : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
        if (nextIndex < 0) return;
        event.preventDefault();
        const nextTab = tabs[nextIndex]!;
        setTab(nextTab.key);
        event.currentTarget.querySelector<HTMLButtonElement>(`#diff-tab-${nextTab.key}`)?.focus();
      }}>
        {tabs.map(({ key, label, icon: Icon }) => (
          <Button
            key={key}
            id={`diff-tab-${key}`}
            role="tab"
            aria-selected={tab === key}
            aria-controls="diff-panel"
            tabIndex={tab === key ? 0 : -1}
            variant={tab === key ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setTab(key)}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </Button>
        ))}
      </div>
      <div id="diff-panel" role="tabpanel" aria-labelledby={`diff-tab-${tab}`} tabIndex={0}>
      {tab === "folders" ? (
        <FoldersDiff />
      ) : tab === "nomenclatures" ? (
        <NomenclatureDiff />
      ) : (
        <CatPartDiff />
      )}
      </div>
    </div>
  );
}
