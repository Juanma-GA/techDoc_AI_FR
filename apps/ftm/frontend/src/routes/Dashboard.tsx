/**
 * Manager (Tableau de bord) — KPIs metier multi-scope. Port React de la vue
 * `manager` de la preview HTML : slicer de perimetre (projets), indicateurs
 * cles, repartition par etat / confiance / severite / type, top fichiers et
 * histogramme empile dans le temps. Donnees via GET /kpis?project_ids=...
 *
 * Note sequencement : les 2 raccourcis « Ouvrir la fiche projet » / « Voir le
 * detail par fichier » seront cables quand leurs destinations existeront
 * (Projects detail = tache 3, Redacteur = tache 4).
 */
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, KpiCard, Slicer } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { OverTimeChart } from "../components/OverTimeChart";
import { PageHeader } from "../components/PageHeader";
import { resources, type KpiOut } from "../lib/api";

const COLOR_CLASS: Record<string, string> = {
  ok: "text-success",
  warn: "text-warning",
  err: "text-danger",
  info: "text-info",
  "": "text-fg",
};

function Colored({ tone, children }: { tone: keyof typeof COLOR_CLASS | string; children: React.ReactNode }) {
  return <span className={COLOR_CLASS[tone] ?? "text-fg"}>{children}</span>;
}

function Bar({ label, value, max, tone }: { label: string; value: number; max: number; tone: string }) {
  const pct = max ? Math.round((100 * value) / max) : 0;
  return (
    <div className="mb-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-fg-dim">{label}</span>
        <span className={`font-mono ${COLOR_CLASS[tone] ?? "text-fg"}`}>{value}</span>
      </div>
      <div className="mt-0.5 h-1.5 overflow-hidden rounded-sm bg-bg-2">
        <div className="h-full bg-brand" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

const STATUS_META = [
  { key: "open", tone: "warn", i18n: "redacteur.statusOpen" },
  { key: "acknowledged", tone: "info", i18n: "redacteur.statusAck" },
  { key: "fixed", tone: "ok", i18n: "redacteur.statusFixed" },
  { key: "rejected", tone: "", i18n: "redacteur.statusRejected" },
] as const;

const CONF_META = [
  { key: "elevee", tone: "ok", i18n: "manager.confHigh" },
  { key: "moyenne", tone: "warn", i18n: "manager.confMedium" },
  { key: "faible", tone: "err", i18n: "manager.confLow" },
] as const;

function ManagerBody({ k, scope }: { k: KpiOut; scope: string[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const oneProject = scope.length === 1;
  const resTone = k.resolution_rate >= 70 ? "ok" : k.resolution_rate >= 40 ? "warn" : "err";

  const sevValues = ["high", "medium", "low"] as const;
  const sevMax = Math.max(1, ...sevValues.map((s) => k.anomalies_by_severity[s] ?? 0));
  const typeKeys = Object.keys(k.anomalies_by_type);
  const typeMax = Math.max(1, ...typeKeys.map((key) => k.anomalies_by_type[key] ?? 0));

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="p-5 pb-0">
          <CardTitle className="text-base">{t("manager.kpis")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <KpiCard
              label={t("manager.openAnomalies")}
              value={<Colored tone={k.open_anomalies === 0 ? "ok" : "warn"}>{k.open_anomalies}</Colored>}
            />
            <KpiCard
              label={t("manager.resolutionRate")}
              value={<Colored tone={resTone}>{k.resolution_rate}%</Colored>}
            />
            <KpiCard
              label={t("manager.totalFiles")}
              value={<Colored tone="info">{k.files_total}</Colored>}
              delta={{ direction: "stable", label: `${k.files_with_anomalies} ${t("manager.withAnomalies")}` }}
            />
            <KpiCard label={t("manager.avgAge")} value={k.avg_age_days} />
            <KpiCard label={t("manager.avgRes")} value={k.avg_resolution_days} />
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="p-5 pb-0">
            <CardTitle className="text-base">{t("manager.byStatus")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {STATUS_META.map((s) => (
                <KpiCard
                  key={s.key}
                  label={t(s.i18n)}
                  value={<Colored tone={s.tone}>{k.anomalies_by_status[s.key] ?? 0}</Colored>}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-5 pb-0">
            <CardTitle className="text-base">{t("manager.byConfidence")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {CONF_META.map((c) => (
                <KpiCard
                  key={c.key}
                  label={t(c.i18n)}
                  value={<Colored tone={c.tone}>{k.anomalies_by_confidence[c.key] ?? 0}</Colored>}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="p-5 pb-0">
            <CardTitle className="text-base">{t("manager.bySeverity")}</CardTitle>
          </CardHeader>
          <CardContent>
            {sevValues.map((s) => (
              <Bar
                key={s}
                label={s}
                value={k.anomalies_by_severity[s] ?? 0}
                max={sevMax}
                tone={s === "high" ? "err" : s === "medium" ? "warn" : ""}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-5 pb-0">
            <CardTitle className="text-base">{t("manager.byType")}</CardTitle>
          </CardHeader>
          <CardContent>
            {typeKeys.length ? (
              typeKeys.map((key) => (
                <Bar key={key} label={key} value={k.anomalies_by_type[key] ?? 0} max={typeMax} tone="" />
              ))
            ) : (
              <div className="py-2 text-center text-fg-muted">—</div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between p-5 pb-0">
          <CardTitle className="text-base">{t("manager.topFiles")}</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={!oneProject}
              title={!oneProject ? t("manager.gotoProjectHint") : undefined}
              onClick={() => { if (scope[0]) navigate(`/projects?pid=${scope[0]}`); }}
            >
              {t("manager.gotoProject")}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { if (scope.length === 1) navigate(`/redacteur?pid=${scope[0]}`); else navigate("/redacteur"); }}
            >
              {t("manager.gotoRedacteur")}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {k.top_files.length ? (
            <div className="flex flex-col gap-1.5">
              {k.top_files.map((f) => (
                <div
                  key={f.filename}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-bg-2 px-3 py-2.5 hover:border-border-bright"
                >
                  <span className="min-w-0 truncate text-sm font-semibold text-fg">{f.filename}</span>
                  <Badge variant="danger">{f.count}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-2 text-center text-fg-muted">—</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-5 pb-0">
          <CardTitle className="text-base">{t("manager.overTime")}</CardTitle>
        </CardHeader>
        <CardContent>
          <OverTimeChart runs={k.anomalies_over_time} />
        </CardContent>
      </Card>
    </div>
  );
}

export function Dashboard() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const pidParam = searchParams.get("pid");
  const [scope, setScope] = useState<string[]>(pidParam ? [pidParam] : []);

  useEffect(() => { if (pidParam) setSearchParams({}, { replace: true }); }, []);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: resources.projects.list,
  });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["kpis", scope],
    queryFn: () => resources.kpis.byScope(scope),
  });

  return (
    <div className="px-8 py-6">
      <PageHeader title={t("nav.manager")} subtitle={t("page.manager")} />

      <Card className="mb-4">
        <CardHeader className="p-5 pb-0">
          <CardTitle className="text-base">{t("manager.selectProject")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-2 text-xs text-fg-dim">{t("common.slicerHint")}</p>
          <Slicer
            items={projects.map((p) => ({ id: p.id, label: p.name }))}
            value={scope}
            onChange={setScope}
            allLabel={t("common.allProjects")}
          />
        </CardContent>
      </Card>

      {isLoading && <p className="text-fg-dim">{t("common.loading")}</p>}

      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-danger/30 bg-card p-4 text-sm text-danger">
          <span>{t("errors.generic")}</span>
          <button type="button" onClick={() => void refetch()} className="underline hover:no-underline">
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && <ManagerBody k={data} scope={scope} />}
    </div>
  );
}
