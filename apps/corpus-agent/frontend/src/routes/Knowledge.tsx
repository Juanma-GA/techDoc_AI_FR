import { Button, CollapsibleSection, Tooltip } from "@internal/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { BrainCircuit, Database, FileCheck2, Files, FolderSync, Info, ListChecks, Network, ShieldCheck, Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { anomaliesApi, filesApi, healthApi, projectsApi, settingsApi } from "../lib/api";
import { resolveAnomalyText } from "../lib/anomalyText";
import { knowledgeCapitalization, knowledgeThemes } from "../lib/knowledgeThemes";
import type { ProjectOut } from "../lib/types";

export function Knowledge() {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState("");
  const [diagramOpen, setDiagramOpen] = useState(false);
  const refreshInterval = diagramOpen ? 5_000 : false;
  const projectsQuery = useQuery<ProjectOut[]>({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = projectsQuery.data ?? [];
  const fileQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["files", project.id],
      queryFn: () => filesApi.list(project.id),
      refetchInterval: refreshInterval,
    })),
  });
  const anomalyQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["anomalies", project.id],
      queryFn: () => anomaliesApi.list(project.id),
    })),
  });
  const connectivityQuery = useQuery({
    queryKey: ["connectivity"], queryFn: healthApi.connectivity,
    enabled: diagramOpen, refetchInterval: refreshInterval, retry: false,
  });
  const rulesQuery = useQuery({
    queryKey: ["rules-legacy"], queryFn: settingsApi.rulesLegacy,
    enabled: diagramOpen, refetchInterval: refreshInterval,
  });
  const healthQuery = useQuery({
    queryKey: ["health"], queryFn: healthApi.read,
    enabled: diagramOpen, refetchInterval: refreshInterval,
  });
  const sourceState = (
    queries: { isError: boolean; isPending: boolean }[],
    count: number,
    activeKey: string,
    emptyKey: string,
  ) => {
    if (projectsQuery.isError || queries.some((query) => query.isError)) return { state: "error", label: t("connectivity.unavailable") };
    if (projectsQuery.isPending || queries.some((query) => query.isPending)) return { state: "loading", label: t("common.loading") };
    return { state: count ? "active" : "inactive", label: t(count ? activeKey : emptyKey, { count }) };
  };
  const sourceStates = [
    ...(["documents", "folder", "reference", "basl"] as const).map((source) => {
      if (connectivityQuery.isError) return { state: "error", label: t("connectivity.unavailable") };
      if (connectivityQuery.isPending) return { state: "loading", label: t("common.loading") };
      const probe = connectivityQuery.data.sources[source];
      return {
        state: probe.unavailable ? "error" : probe.available ? "active" : "inactive",
        label: t(probe.unavailable ? "connectivity.accessFailed" : probe.available ? "connectivity.accessible" : "connectivity.notConfigured", { count: probe.available, total: probe.configured, failed: probe.unavailable }),
      };
    }),
    sourceState([rulesQuery], (rulesQuery.data?.rules.regles_personnalisees ?? rulesQuery.data?.rules.custom_rules ?? []).filter((rule) => rule.enabled !== false && rule.validated !== false).length, "connectivity.activeRules", "connectivity.noRules"),
  ];

  const knowledge = useMemo(() => {
    return projects.flatMap((project, index) => {
      const files = fileQueries[index]?.data ?? [];
      const anomalies = anomalyQueries[index]?.data ?? [];
      const filenames = new Map(
        files.flatMap((file) => file.versions.map((version) => [version.id, { filename: version.filename, sourceId: file.id }] as const)),
      );
      return anomalies
        .map((anomaly) => ({
          anomaly: {
            ...anomaly,
            message: resolveAnomalyText(t, anomaly.message, anomaly.message_key, anomaly.message_params_json),
            suggestion: resolveAnomalyText(t, anomaly.suggestion, anomaly.suggestion_key, anomaly.suggestion_params_json),
          },
          project: project.name,
          filename: anomaly.file_version_id ? filenames.get(anomaly.file_version_id)?.filename ?? "" : "",
          sourceId: anomaly.file_version_id ? filenames.get(anomaly.file_version_id)?.sourceId ?? null : null,
        }));
    });
  }, [projects, fileQueries, anomalyQueries, t]);

  const needle = search.trim().toLocaleLowerCase();
  const matchingKnowledge = knowledge.filter(({ anomaly, project, filename }) =>
    !needle || [project, filename, anomaly.category, anomaly.message, anomaly.suggestion, anomaly.evidence]
      .some((value) => value?.toLocaleLowerCase().includes(needle)),
  );
  const themes = knowledgeThemes(matchingKnowledge, i18n.language);
  const capital = knowledgeCapitalization(knowledge, i18n.language);
  const correctionCount = themes.reduce((count, theme) => count + theme.corrections.length, 0);
  const isLoading = projectsQuery.isLoading || [...fileQueries, ...anomalyQueries].some((query) => query.isLoading);
  const error = projectsQuery.error ?? [...fileQueries, ...anomalyQueries].find((query) => query.error)?.error;

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.knowledge")}</h1>
        <p>{t("knowledge.description")}</p>
      </div>
      <CollapsibleSection title={t("connectivity.title")} open={diagramOpen} onOpenChange={setDiagramOpen} className="mb-4">
        <p>{t("connectivity.description")}</p>
        <p className="text-sm text-fg-dim">{t("connectivity.statusScope")}</p>
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <Button variant="secondary" size="sm" disabled={connectivityQuery.isFetching} onClick={() => void connectivityQuery.refetch()}>
            {t("connectivity.refresh")}
          </Button>
          {connectivityQuery.data && <span className="text-xs text-fg-dim">
            {t("connectivity.checkedAt", { time: new Date(connectivityQuery.data.checked_at).toLocaleTimeString(i18n.language) })}
          </span>}
          {connectivityQuery.isError && <span role="alert" className="error">{connectivityQuery.error.message}</span>}
        </div>
        <div className="flex flex-wrap gap-3 text-xs mb-3">
          <span className="connectivity-state" data-state="active">{t("connectivity.available")}</span>
          <span className="connectivity-state" data-state="inactive">{t("connectivity.absent")}</span>
          <span className="connectivity-state" data-state="error">{t("connectivity.unavailable")}</span>
        </div>
        <figure aria-label={t("connectivity.title")} className="connectivity-map">
          <div className="connectivity-canvas">
            <svg className="connectivity-links" viewBox="0 0 1000 560" preserveAspectRatio="none" aria-hidden="true">
              {[100, 190, 280, 370, 460].map((y, index) => <g key={y} data-state={sourceStates[index]?.state}>
                <path d={`M 300 ${y} C 365 ${y}, 345 280, 390 280`} />
                <circle cx="300" cy={y} r="4" />
              </g>)}
              <path d="M 610 280 C 670 280, 640 140, 700 140" />
              <path d="M 840 180 L 840 240 M 840 320 L 840 380" />
              <path className="connectivity-loop" d="M 840 460 C 840 540, 500 540, 500 365" />
              <circle cx="700" cy="140" r="4" />
            </svg>
            <h2 className="connectivity-heading connectivity-heading-input">{t("connectivity.inputs")}</h2>
            <h2 className="connectivity-heading connectivity-heading-output">{t("connectivity.outputs")}</h2>
              {([
                ["documents", Files],
                ["folder", FolderSync],
                ["reference", Database],
                ["basl", Wrench],
                ["rules", ListChecks],
              ] as const).map(([source, Icon], index) => (
                <div key={source} className="connectivity-node connectivity-source" data-state={sourceStates[index]?.state} style={{ top: `${(100 + index * 90) / 5.6}%` }}>
                  <span className="connectivity-icon"><Icon size={20} aria-hidden="true" /></span>
                  <span className="connectivity-node-label">
                    {t(`connectivity.${source}`)}
                    <span className="connectivity-state" data-state={sourceStates[index]?.state} role="status">{sourceStates[index]?.label}</span>
                  </span>
                    <Tooltip content={t(`connectivity.${source}Trigger`)}>
                      <Button variant="ghost" size="icon" aria-label={t("connectivity.triggerLabel", { source: t(`connectivity.${source}`) })}>
                        <Info size={16} aria-hidden="true" />
                      </Button>
                    </Tooltip>
                </div>
              ))}
              <div className="connectivity-hub">
                <span className="connectivity-hub-icon"><BrainCircuit size={36} aria-hidden="true" /></span>
                <h2 className="card-title">{t("app.title")}</h2>
                <span className="connectivity-state" data-state={healthQuery.isError ? "error" : healthQuery.isPending ? "loading" : healthQuery.data?.status === "ok" ? "active" : "inactive"} role="status">
                  {t(healthQuery.isError ? "connectivity.unavailable" : healthQuery.isPending ? "common.loading" : healthQuery.data?.status === "ok" ? "connectivity.responding" : "connectivity.degraded")}
                </span>
                <Network size={20} aria-hidden="true" className="mx-auto text-fg-dim" />
                <p className="text-sm">{t("connectivity.engine")}</p>
                <p className="text-xs text-fg-dim">{t("connectivity.llm")}</p>
                <p className="connectivity-state" role="status" data-state={connectivityQuery.isError ? "error" : connectivityQuery.isPending ? "loading" : !connectivityQuery.data.ai_enabled ? "inactive" : connectivityQuery.data.ai_connection === "connected" ? "active" : "error"}>
                  {t(connectivityQuery.isError ? "connectivity.unavailable" : connectivityQuery.isPending ? "common.loading" : connectivityQuery.data.ai_enabled ? "connectivity.aiEnabled" : "connectivity.aiDisabled")}
                </p>
                {connectivityQuery.data && !connectivityQuery.isError && <p className="text-xs text-fg-dim">
                  {t(`connectivity.ai.${connectivityQuery.data.ai_connection}`)}
                </p>}
              </div>
              {([
                ["findings", FileCheck2],
                ["review", ShieldCheck],
                ["memory", BrainCircuit],
              ] as const).map(([output, Icon], index) => (
                <div className="connectivity-node connectivity-output" key={output} style={{ top: `${25 + index * 25}%` }}>
                  <span className="connectivity-icon"><Icon size={22} aria-hidden="true" /></span>
                  <span className="connectivity-node-label">{t(`connectivity.${output}`)}</span>
                </div>
              ))}
          </div>
          <figcaption className="mt-4">
            <p>{t("connectivity.feedback")}</p>
            <p className="label">{t("connectivity.limits")}</p>
          </figcaption>
        </figure>
      </CollapsibleSection>
      {!isLoading && !error && <section className="card" aria-label={t("knowledge.capitalTitle")}>
        <h2 className="card-title">{t("knowledge.capitalTitle")}</h2>
        <p>{t("knowledge.capitalScope")}</p>
        <div className="kpi-grid">
          {([
            ["knowledge.correctionsMetric", capital.correctionCount],
            ["knowledge.lessonsMetric", capital.lessonCount],
            ["knowledge.sourcesMetric", capital.sourceCount],
            ["knowledge.themesMetric", capital.themeCount],
          ] as const).map(([label, count]) => <div className="kpi" key={label}>
            <div className="label">{t(label)}</div>
            <div className="kpi-value info">{count}</div>
          </div>)}
        </div>
        <p>{t("knowledge.capitalPipeline", { corrections: capital.correctionCount, lessons: capital.lessonCount, themes: capital.themeCount })}</p>
        <p>{t("knowledge.formalize", { count: capital.toFormalize })}</p>
        <CollapsibleSection title={t("knowledge.growth")} defaultOpen={false}>
          <p>{t("knowledge.growthScope")}</p>
          {capital.timeline.length ? <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr>
                <th scope="col">{t("knowledge.date")}</th>
                <th scope="col">{t("knowledge.added")}</th>
                <th scope="col">{t("knowledge.cumulative")}</th>
              </tr></thead>
              <tbody>{capital.timeline.map((point) => <tr key={point.day}>
                <th scope="row">{new Date(`${point.day}T00:00:00Z`).toLocaleDateString(i18n.language, { timeZone: "UTC" })}</th>
                <td>+{point.added}</td>
                <td>{point.cumulative}</td>
              </tr>)}</tbody>
            </table>
          </div> : <p>{t("knowledge.noDates")}</p>}
          {capital.undatedCount > 0 && <p>{t("knowledge.undated", { count: capital.undatedCount })}</p>}
        </CollapsibleSection>
        <p className="label">{t("knowledge.learningScope")}</p>
      </section>}
      <div className="card">
        <label className="grow">
          <span className="label">{t("knowledge.searchLabel")}</span>
          <input
            className="input"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("knowledge.searchPlaceholder")}
          />
        </label>
      </div>
      {error && <div className="card" role="alert"><div className="error">{error.message}</div></div>}
      {isLoading ? (
        <div className="card"><div className="empty-state">{t("common.loading")}</div></div>
      ) : error ? null : themes.length === 0 ? (
        <div className="card"><div className="empty-state">{t("knowledge.empty")}</div></div>
      ) : (
        <>
          <div className="label">{t("knowledge.themeCount", { count: themes.length })} · {t("knowledge.count", { count: correctionCount })}</div>
          {themes.map((theme) => (
            <article className="card" key={theme.key}>
              <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
                <h2 className="card-title">{theme.title || t("knowledge.uncategorized")}</h2>
                <span className="badge">{t("knowledge.count", { count: theme.corrections.length })}</span>
              </div>
              <p>{t("knowledge.coverage", { files: theme.sourceCount, projects: theme.projectCount })}</p>
              <h3>{t("knowledge.lessons")}</h3>
              {theme.lessons.length ? <ul>
                {theme.lessons.map((lesson) => <li key={lesson.text}>
                  {lesson.text} <span className="label">({t("knowledge.support", { count: lesson.count })})</span>
                </li>)}
              </ul> : <p>{t("knowledge.noLesson")}</p>}
              <p>{t("knowledge.pending", { count: theme.pendingCount })}</p>
              {theme.latest && <p className="label">
                {t("knowledge.updatedAt", { date: new Date(theme.latest).toLocaleDateString(i18n.language) })}
              </p>}
              <CollapsibleSection title={t("knowledge.provenance")} defaultOpen={false}>
                {theme.corrections.map(({ anomaly, project, filename }) => <article key={anomaly.id} className="mb-4">
                  <div className="label">{project}{filename ? ` · ${filename}` : ""}</div>
                  <p>{anomaly.message}</p>
                  {anomaly.evidence && (
                    <div className="red-anomaly-evidence">
                      <strong>{t("redacteur.evidenceLabel")}</strong> {anomaly.evidence}
                    </div>
                  )}
                  {anomaly.location && <div className="red-anomaly-loc">{anomaly.location}</div>}
                  {anomaly.suggestion && (
                    <div className="red-anomaly-suggestion">
                      <strong>{t("knowledge.resolution")}</strong> {anomaly.suggestion}
                    </div>
                  )}
                  {anomaly.resolved_at && (
                    <div className="label" style={{ marginTop: 8 }}>
                      {t("knowledge.resolvedAt", { date: new Date(anomaly.resolved_at).toLocaleDateString(i18n.language) })}
                    </div>
                  )}
                </article>)}
              </CollapsibleSection>
            </article>
          ))}
        </>
      )}
    </>
  );
}
