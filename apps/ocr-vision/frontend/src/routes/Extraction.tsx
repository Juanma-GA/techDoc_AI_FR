import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ExtractionTable } from "./ExtractionTable";
import {
  projectTablesApi,
  projectsApi,
  templatesApi,
  type ProjectDto,
  type ProjectTableDto,
  type TemplateDto,
} from "../lib/api";

export function Extraction() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [projectId, setProjectId] = useState<string>("");
  const [tableId, setTableId] = useState<string>("");
  const [newProject, setNewProject] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [tableName, setTableName] = useState("");

  const projectsQuery = useQuery<ProjectDto[]>({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const templatesQuery = useQuery<TemplateDto[]>({
    queryKey: ["templates"],
    queryFn: templatesApi.list,
  });
  const tablesQuery = useQuery<ProjectTableDto[]>({
    queryKey: ["project-tables", projectId],
    queryFn: () => projectTablesApi.list(projectId),
    enabled: !!projectId,
  });

  const createProject = useMutation({
    mutationFn: () => projectsApi.create(newProject.trim()),
    onSuccess: (p) => {
      setNewProject("");
      setProjectId(p.id);
      void qc.invalidateQueries({ queryKey: ["projects"] });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
  });

  const attachTable = useMutation({
    mutationFn: () =>
      projectTablesApi.create({
        project_id: projectId,
        template_id: templateId,
        name: tableName.trim() || undefined,
      }),
    onSuccess: (tbl) => {
      setTemplateId("");
      setTableName("");
      setTableId(tbl.id);
      void qc.invalidateQueries({ queryKey: ["project-tables", projectId] });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
  });

  const tables = tablesQuery.data ?? [];
  const selectedTable = tables.find((x) => x.id === tableId) ?? null;
  const templates = templatesQuery.data ?? [];

  return (
    <>
      <div className="page-header">
        <h1>{t("routes.extraction.title")}</h1>
        <p>{t("routes.extraction.sub")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("extraction.projectsTitle")}</h2>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="grow">
            <div className="label">{t("extraction.selectProject")}</div>
            <select
              className="input"
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value);
                setTableId("");
              }}
            >
              <option value="">—</option>
              {(projectsQuery.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <input
            className="input grow"
            value={newProject}
            placeholder={t("extraction.projectPlaceholder")}
            onChange={(e) => setNewProject(e.target.value)}
          />
          <button
            type="button"
            className="btn secondary"
            disabled={!newProject.trim() || createProject.isPending}
            onClick={() => createProject.mutate()}
          >
            {t("extraction.createProject")}
          </button>
        </div>
        {!projectsQuery.data?.length ? (
          <div className="empty-state">{t("extraction.noProject")}</div>
        ) : null}
      </div>

      {projectId ? (
        <div className="card">
          <h2 className="card-title">{t("extraction.tablesTitle")}</h2>
          {tables.length ? (
            <div className="file-list">
              {tables.map((tbl) => (
                <button
                  type="button"
                  key={tbl.id}
                  className={tbl.id === tableId ? "file-row selected" : "file-row"}
                  onClick={() => setTableId(tbl.id)}
                >
                  <div className="grow">
                    <div className="file-name">{tbl.name}</div>
                    <div className="file-meta">
                      {t("extraction.rowsCount", { n: tbl.row_count })}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state">{t("extraction.noTable")}</div>
          )}

          <div className="card-title" style={{ marginTop: 14 }}>
            {t("extraction.attachTitle")}
          </div>
          {templates.length ? (
            <div className="row" style={{ alignItems: "flex-end" }}>
              <label className="grow">
                <div className="label">{t("extraction.chooseTemplate")}</div>
                <select
                  className="input"
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                >
                  <option value="">—</option>
                  {templates.map((tpl) => (
                    <option key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </option>
                  ))}
                </select>
              </label>
              <input
                className="input grow"
                value={tableName}
                placeholder={t("extraction.tableNamePlaceholder")}
                onChange={(e) => setTableName(e.target.value)}
              />
              <button
                type="button"
                className="btn secondary"
                disabled={!templateId || attachTable.isPending}
                onClick={() => attachTable.mutate()}
              >
                {t("extraction.attach")}
              </button>
            </div>
          ) : (
            <div className="empty-state">{t("extraction.noTemplate")}</div>
          )}
        </div>
      ) : null}

      {selectedTable ? (
        <ExtractionTable tableId={selectedTable.id} columns={selectedTable.columns} />
      ) : null}
    </>
  );
}
