import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { z } from "zod";

import { ApiClientError, projectsApi } from "../lib/api";
import { fmtDate } from "../lib/format";
import type { ProjectOut } from "../lib/types";

const schema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(4000).optional(),
  vision_enabled: z.boolean().optional(),
});
type FormValues = z.infer<typeof schema>;

export function Projects() {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || "fr").slice(0, 2);
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const projectsQuery = useQuery<ProjectOut[]>({ queryKey: ["projects"], queryFn: projectsApi.list });
  const { register, handleSubmit, reset, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", vision_enabled: false },
  });

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      projectsApi.create({ name: v.name.trim(), description: (v.description ?? "").trim(), vision_enabled: !!v.vision_enabled }),
    onSuccess: () => {
      reset({ name: "", description: "", vision_enabled: false });
      setError(null);
      void qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : String(e)),
  });

  const projects = projectsQuery.data ?? [];

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.projects")}</h1>
        <p>{t("page.projects")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("projects.new")}</h2>
        <form className="form" onSubmit={handleSubmit((v) => create.mutate(v))}>
          <input className="input" placeholder={t("projects.namePh")} {...register("name")} />
          <input className="input" placeholder={t("projects.descPh")} {...register("description")} />
          <label className="checkbox">
            <input type="checkbox" {...register("vision_enabled")} />
            {t("projects.vision")}
          </label>
          <div className="row">
            <button type="submit" className="btn primary" disabled={create.isPending || !formState.isValid}>
              {t("projects.create")}
            </button>
            {error && <span className="error">{error}</span>}
          </div>
        </form>
      </div>

      <div className="card">
        <h2 className="card-title">{t("projects.list")}</h2>
        {projectsQuery.isLoading ? (
          <div className="empty-state">{t("common.loading")}</div>
        ) : projects.length === 0 ? (
          <div className="empty-state">{t("common.empty")}</div>
        ) : (
          <div className="project-list">
            {projects.map((p) => (
              <Link className="project-row" to={`/projects/${p.id}`} key={p.id}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="project-name">{p.name}</div>
                  {p.description && <div className="project-desc">{p.description}</div>}
                  <div className="project-meta">
                    <span className="label">{fmtDate(p.created_at, lang)}</span>
                    {p.vision_enabled && <span className="badge info">vision</span>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
