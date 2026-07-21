import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ExtractionTable } from "./ExtractionTable";
import { RenameInline } from "./RenameInline";
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

  const renameProject = useMutation({
    mutationFn: (name: string) => projectsApi.rename(projectId, name),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["projects"] }),
  });

  const renameTable = useMutation({
    mutationFn: (name: string) => projectTablesApi.rename(tableId, name),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["project-tables", projectId] }),
  });

  const projects = projectsQuery.data ?? [];
  const selectedProject = projects.find((p) => p.id === projectId) ?? null;
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
        {projects.length ? (
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {projects.map((p) => (
              <button
                type="button"
                key={p.id}
                className={p.id === projectId ? "btn primary" : "btn ghost"}
                aria-pressed={p.id === projectId}
                onClick={() => {
                  setProjectId(p.id);
                  setTableId("");
                }}
              >
                {p.name}
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t("extraction.noProject")}</div>
        )}
        {selectedProject ? (
          <RenameInline
            key={selectedProject.name}
            current={selectedProject.name}
            pending={renameProject.isPending}
            error={renameProject.isError ? (renameProject.error as Error).message : ""}
            onSave={(name) => renameProject.mutate(name)}
          />
        ) : null}
        <div className="row" style={{ alignItems: "flex-end", marginTop: 12 }}>
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
      </div>

      {projectId ? (
        <div className="card">
          <h2 className="card-title">{t("extraction.tablesTitle")}</h2>
          {tables.length ? (
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              {tables.map((tbl) => (
                <button
                  type="button"
                  key={tbl.id}
                  className={tbl.id === tableId ? "btn primary" : "btn ghost"}
                  aria-pressed={tbl.id === tableId}
                  title={t("extraction.rowsCount", { n: tbl.row_count })}
                  onClick={() => setTableId(tbl.id)}
                >
                  {tbl.name} ({tbl.row_count})
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state">{t("extraction.noTable")}</div>
          )}
          {selectedTable ? (
            <RenameInline
              key={selectedTable.name}
              current={selectedTable.name}
              pending={renameTable.isPending}
              error={renameTable.isError ? (renameTable.error as Error).message : ""}
              onSave={(name) => renameTable.mutate(name)}
            />
          ) : null}

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
