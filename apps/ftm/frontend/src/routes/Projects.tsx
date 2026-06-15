import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import { resources, type Project } from "../lib/api";

function CreateForm({ onCancel }: { onCancel: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [vision, setVision] = useState(false);

  const mutation = useMutation({
    mutationFn: resources.projects.create,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      onCancel();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    mutation.mutate({ name: name.trim(), description, vision_enabled: vision });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-6 rounded-lg border bg-card p-5 shadow-card"
    >
      <div className="mb-3">
        <label className="mb-1 block text-sm font-medium text-fg">
          {t("projects.name")}
        </label>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("projects.namePlaceholder")}
          className="w-full rounded-md border bg-bg px-3 py-2 text-sm text-fg placeholder-fg-dim focus:outline-none focus:ring-2 focus:ring-brand-blue-light"
          maxLength={255}
          required
        />
      </div>
      <div className="mb-3">
        <label className="mb-1 block text-sm font-medium text-fg">
          {t("projects.description")}
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("projects.descriptionPlaceholder")}
          rows={2}
          className="w-full rounded-md border bg-bg px-3 py-2 text-sm text-fg placeholder-fg-dim focus:outline-none focus:ring-2 focus:ring-brand-blue-light"
          maxLength={4000}
        />
      </div>
      <label className="mb-4 flex cursor-pointer items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={vision}
          onChange={(e) => setVision(e.target.checked)}
          className="h-4 w-4 rounded"
        />
        {t("projects.visionEnabled")}
      </label>
      {mutation.isError && (
        <p className="mb-3 text-sm text-red-400">{t("errors.generic")}</p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={mutation.isPending || !name.trim()}
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-fg shadow-card transition-colors hover:bg-brand-blue-light disabled:opacity-50"
        >
          {mutation.isPending ? t("common.loading") : t("projects.create")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border px-4 py-2 text-sm font-medium text-fg-dim transition-colors hover:text-fg"
        >
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function ProjectRow({ project }: { project: Project }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [armed, setArmed] = useState(false);
  const [armTimer, setArmTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  const deleteMutation = useMutation({
    mutationFn: () => resources.projects.delete(project.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["projects"] }),
  });

  const handleDelete = () => {
    if (armed) {
      if (armTimer) clearTimeout(armTimer);
      setArmed(false);
      deleteMutation.mutate();
    } else {
      if (armTimer) clearTimeout(armTimer);
      setArmed(true);
      const t = setTimeout(() => setArmed(false), 3000);
      setArmTimer(t);
    }
  };

  const date = new Date(project.created_at).toLocaleDateString();

  return (
    <div className="flex items-center justify-between rounded-lg border bg-card px-5 py-4 shadow-card">
      <div className="min-w-0">
        <p className="truncate font-medium text-fg">{project.name}</p>
        {project.description && (
          <p className="mt-0.5 truncate text-sm text-fg-dim">{project.description}</p>
        )}
        <p className="mt-1 text-xs text-fg-dim">
          {t("projects.createdAt")} {date}
          {project.vision_enabled && (
            <span className="ml-2 rounded bg-brand/20 px-1.5 py-0.5 text-xs text-brand-blue-light">
              Vision
            </span>
          )}
        </p>
      </div>
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleteMutation.isPending}
        className={[
          "ml-4 shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
          armed
            ? "bg-red-600 text-white hover:bg-red-700"
            : "border text-fg-dim hover:border-red-500 hover:text-red-400",
        ].join(" ")}
      >
        {armed ? t("projects.deleteArm") : t("common.delete")}
      </button>
    </div>
  );
}

export function Projects() {
  const { t } = useTranslation();
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: resources.projects.list,
  });

  return (
    <div className="px-8 py-6">
      <div className="mb-6 flex items-start justify-between">
        <PageHeader
          title={t("routes.projects.title")}
          subtitle={t("routes.projects.subtitle")}
        />
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="shrink-0 rounded-md bg-brand px-4 py-2 text-sm font-medium text-fg shadow-card transition-colors hover:bg-brand-blue-light"
          >
            {t("projects.new")}
          </button>
        )}
      </div>

      {showForm && <CreateForm onCancel={() => setShowForm(false)} />}

      {isLoading && <p className="text-fg-dim">{t("common.loading")}</p>}

      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-card p-4 text-sm text-red-400">
          <span>{t("errors.generic")}</span>
          <button type="button" onClick={() => void refetch()} className="underline hover:no-underline">
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && data.length === 0 && !showForm && (
        <div className="rounded-lg border bg-card p-8 text-center text-fg-dim shadow-card">
          {t("projects.empty")}
        </div>
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col gap-3">
          {data.map((p) => (
            <ProjectRow key={p.id} project={p} />
          ))}
        </div>
      )}
    </div>
  );
}
