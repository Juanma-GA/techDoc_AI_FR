import { Lock, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import {
  useCreateStandard,
  useCreateVersion,
  useDeleteStandard,
  useDeleteVersion,
  useStandardVersionDetail,
  useStandards,
} from "../hooks/useStandards";
import type { Standard } from "../types/domain";

export function Standards(): JSX.Element {
  const { t } = useTranslation();
  const standards = useStandards();
  const createStd = useCreateStandard();
  const createVer = useCreateVersion();
  const deleteStd = useDeleteStandard();
  const deleteVer = useDeleteVersion();

  const items: Standard[] = standards.data ?? [];

  const [selectedStd, setSelectedStd] = useState<string | null>(null);
  const [selectedVer, setSelectedVer] = useState<string | null>(null);
  const [draftCode, setDraftCode] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [draftVersion, setDraftVersion] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Standard | null>(null);

  const current = useMemo(
    () => items.find((s) => s.id === selectedStd) ?? items[0] ?? null,
    [items, selectedStd],
  );
  const versions = current?.versions ?? [];
  const activeVersion = useMemo(
    () => versions.find((v) => v.id === selectedVer) ?? versions[0] ?? null,
    [versions, selectedVer],
  );
  const detail = useStandardVersionDetail(
    current?.id ?? null,
    activeVersion?.id ?? null,
  );

  const submitStandard = (): void => {
    if (!draftCode.trim() || !draftLabel.trim()) return;
    createStd.mutate(
      { code: draftCode.trim(), label: draftLabel.trim() },
      {
        onSuccess: () => {
          setDraftCode("");
          setDraftLabel("");
        },
      },
    );
  };

  const submitVersion = (): void => {
    if (!current || current.builtin || !draftVersion.trim()) return;
    createVer.mutate(
      { standardId: current.id, label: draftVersion.trim() },
      { onSuccess: () => setDraftVersion("") },
    );
  };

  return (
    <div className="flex flex-col">
      <PageHeader title={t("standards.title")} subtitle={t("standards.subtitle")} />

      <section className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-[260px_1fr]">
        <aside className="flex flex-col gap-3">
          <h2 className="font-display text-sm text-fg-dim">{t("standards.listTitle")}</h2>
          {standards.isLoading ? (
            <p className="text-fg-dim">{t("common.loading")}</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {items.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedStd(s.id);
                      setSelectedVer(s.versions[0]?.id ?? null);
                    }}
                    className={[
                      "flex w-full items-center justify-between gap-2 rounded-sm px-3 py-2 text-left",
                      (current?.id ?? null) === s.id
                        ? "bg-brand text-fg"
                        : "text-fg-dim hover:bg-card-hover",
                    ].join(" ")}
                  >
                    <span className="font-mono">{s.code}</span>
                    {s.builtin ? (
                      <Lock size={12} aria-label={t("standards.builtin")} />
                    ) : (
                      <button
                        type="button"
                        aria-label={t("common.delete")}
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDelete(s);
                        }}
                        className="rounded-sm p-1 hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4 flex flex-col gap-2 rounded-sm border bg-card p-3">
            <h3 className="font-display text-xs text-fg">{t("standards.createCustom")}</h3>
            <input
              placeholder={t("standards.codePlaceholder")}
              value={draftCode}
              onChange={(e) => setDraftCode(e.target.value)}
              className="rounded-sm border bg-bg-2 px-2 py-1 font-mono text-xs text-fg"
            />
            <input
              placeholder={t("standards.labelPlaceholder")}
              value={draftLabel}
              onChange={(e) => setDraftLabel(e.target.value)}
              className="rounded-sm border bg-bg-2 px-2 py-1 text-xs text-fg"
            />
            <button
              type="button"
              onClick={submitStandard}
              disabled={createStd.isPending || !draftCode || !draftLabel}
              className="inline-flex items-center justify-center gap-1 rounded-sm bg-brand px-2 py-1 text-xs text-fg hover:bg-brand-blue-light disabled:opacity-50"
            >
              <Plus size={12} />
              {t("standards.create")}
            </button>
          </div>
        </aside>

        <article className="flex flex-col gap-4">
          {current ? (
            <>
              <header className="flex items-baseline justify-between">
                <div>
                  <h2 className="font-display text-fg">{current.label}</h2>
                  <p className="text-xs text-fg-dim">{current.description}</p>
                </div>
                <span className="label">
                  {current.builtin ? t("standards.builtin") : t("standards.custom")}
                </span>
              </header>

              <div className="flex flex-wrap items-center gap-2">
                {versions.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setSelectedVer(v.id)}
                    className={[
                      "rounded-sm px-3 py-1 text-xs",
                      (activeVersion?.id ?? null) === v.id
                        ? "bg-brand text-fg"
                        : "border text-fg-dim hover:bg-card-hover",
                    ].join(" ")}
                  >
                    {v.label}
                    {!v.builtin ? ` (${t("standards.custom")})` : ""}
                  </button>
                ))}
                {!current.builtin ? (
                  <>
                    <input
                      placeholder={t("standards.versionPlaceholder")}
                      value={draftVersion}
                      onChange={(e) => setDraftVersion(e.target.value)}
                      className="rounded-sm border bg-bg-2 px-2 py-1 text-xs text-fg"
                    />
                    <button
                      type="button"
                      onClick={submitVersion}
                      disabled={createVer.isPending || !draftVersion}
                      className="inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs text-fg-dim hover:bg-card-hover disabled:opacity-50"
                    >
                      <Plus size={12} />
                      {t("standards.addVersion")}
                    </button>
                  </>
                ) : null}
                {activeVersion && !activeVersion.builtin ? (
                  <button
                    type="button"
                    onClick={() =>
                      deleteVer.mutate({
                        standardId: current.id,
                        versionId: activeVersion.id,
                      })
                    }
                    className="rounded-sm border px-2 py-1 text-xs text-danger hover:bg-danger/10"
                  >
                    {t("standards.deleteVersion")}
                  </button>
                ) : null}
              </div>

              <section className="rounded-sm border bg-card p-4">
                <h3 className="font-display text-sm text-fg">{t("standards.catalogTitle")}</h3>
                {detail.isLoading ? (
                  <p className="text-fg-dim">{t("common.loading")}</p>
                ) : detail.data && detail.data.catalog.length > 0 ? (
                  <ul className="mt-3 flex flex-col gap-2">
                    {detail.data.catalog.map((c) => (
                      <li
                        key={c.code}
                        className="flex flex-col gap-1 rounded-sm border bg-bg-2 p-3"
                      >
                        <p className="flex items-baseline justify-between gap-2 font-mono text-xs">
                          <span className="text-fg">{c.code}</span>
                          <span className="label">{c.kind} · {c.severity}</span>
                        </p>
                        <p className="text-sm text-fg">{c.title}</p>
                        <p className="text-xs text-fg-dim">{c.description}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-fg-dim">{t("standards.catalogEmpty")}</p>
                )}
              </section>
            </>
          ) : (
            <p className="text-fg-dim">{t("standards.selectStandard")}</p>
          )}
        </article>
      </section>

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDelete(null);
        }}
        title={t("standards.confirmDelete")}
        description={confirmDelete?.label}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (confirmDelete) deleteStd.mutate(confirmDelete.id);
          setConfirmDelete(null);
        }}
      />
    </div>
  );
}
