import { useDemoMode } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { AnalysisCard } from "../components/project/AnalysisCard";
import { FilesCard } from "../components/project/FilesCard";
import { ReferenceCard } from "../components/project/ReferenceCard";
import { useDoubleClickConfirm } from "../hooks/useDoubleClickConfirm";
import { ApiClientError, projectsApi } from "../lib/api";
import { fmtDate } from "../lib/format";
import { useScopeStore } from "../stores/useScopeStore";
import type { ProjectOut } from "../lib/types";

export function ProjectDetail() {
  const { t, i18n } = useTranslation();
  const { mode, isReady } = useDemoMode();
  const lang = (i18n.language || "fr").slice(0, 2);
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const setManagerScope = useScopeStore((s) => s.setManagerScope);

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", vision_enabled: false });

  const projectQuery = useQuery<ProjectOut>({ queryKey: ["project", id], queryFn: () => projectsApi.get(id) });
  const p = projectQuery.data;
  useEffect(() => {
    if (p) setForm({ name: p.name, description: p.description, vision_enabled: p.vision_enabled });
  }, [p]);

  const update = useMutation({
    mutationFn: () => projectsApi.update(id, form),
    onSuccess: () => {
      setEditing(false);
      void qc.invalidateQueries({ queryKey: ["project", id] });
      void qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const remove = useMutation({
    mutationFn: () => projectsApi.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      navigate("/projects");
    },
  });
  const del = useDoubleClickConfirm(() => remove.mutate(), 3000);

  if (mode === "demo" && projectQuery.error instanceof ApiClientError && projectQuery.error.status === 404) {
    return <Navigate to="/projects" replace />;
  }

  if (projectQuery.isLoading || !p) {
    return (
      <>
        <div className="page-header"><h1>{t("nav.projects")}</h1></div>
        <div className="card"><div className="empty-state">{t("common.loading")}</div></div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>{p.name}</h1>
        <p>
          <button type="button" className="btn ghost small" onClick={() => navigate("/projects")}>
            {t("projects.back")}
          </button>
        </p>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="card-title">{p.name}</h2>
          <div className="row">
            <button type="button" className="btn secondary small" onClick={() => { setManagerScope([id]); navigate("/"); }}>
              {t("projects.dashboard")}
            </button>
            {isReady && mode === "normal" && (
              <>
                <button type="button" className="btn secondary small" onClick={() => setEditing((e) => !e)}>
                  {t("projects.edit")}
                </button>
                <button type="button" className="btn danger small" onClick={del.handleClick}>
                  {del.armed ? t("common.confirmDelete") : t("projects.delete")}
                </button>
              </>
            )}
          </div>
        </div>

        {editing ? (
          <form className="form" onSubmit={(e) => { e.preventDefault(); update.mutate(); }}>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <label className="checkbox">
              <input type="checkbox" checked={form.vision_enabled} onChange={(e) => setForm({ ...form, vision_enabled: e.target.checked })} />
              {t("projects.vision")}
            </label>
            <div className="row">
              <button type="submit" className="btn primary small" disabled={update.isPending}>{t("projects.save")}</button>
              <button type="button" className="btn ghost small" onClick={() => setEditing(false)}>{t("projects.cancel")}</button>
            </div>
          </form>
        ) : (
          <div className="kpi-grid">
            <div className="kpi"><div className="label">{t("projects.descPh")}</div><div>{p.description || "—"}</div></div>
            <div className="kpi"><div className="label">vision</div><div className={`badge ${p.vision_enabled ? "ok" : "off"}`}>{p.vision_enabled ? "ON" : "OFF"}</div></div>
            <div className="kpi"><div className="label">{fmtDate(p.created_at, lang)}</div><div className="label">{p.id.slice(0, 8)}</div></div>
          </div>
        )}
      </div>

      <ReferenceCard pid={id} />
      <FilesCard pid={id} />
      <AnalysisCard pid={id} />
    </>
  );
}
