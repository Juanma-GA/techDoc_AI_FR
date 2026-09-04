import { Lock, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "../components/ConfirmDialog";
import {
  useCreateStandard,
  useCreateVersion,
  useDeleteStandard,
  useDeleteVersion,
  useStandardVersionDetail,
  useStandards,
} from "../hooks/useStandards";
import type { Standard } from "../types/domain";

/**
 * Administration des normes : liste des normes (built-in + custom), versions,
 * et **catalogue de regles en lecture seule** par version. Les regles custom se
 * gerent desormais dans la carte « Regles custom » dediee (retirees d'ici).
 */
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
  const [draftDescription, setDraftDescription] = useState("");
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
  const detail = useStandardVersionDetail(current?.id ?? null, activeVersion?.id ?? null);

  const submitStandard = (): void => {
    if (!draftCode.trim() || !draftLabel.trim()) return;
    const description = draftDescription.trim();
    createStd.mutate(
      {
        code: draftCode.trim(),
        label: draftLabel.trim(),
        ...(description ? { description } : {}),
      },
      {
        onSuccess: () => {
          setDraftCode("");
          setDraftLabel("");
          setDraftDescription("");
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
    <div className="card">
      <section
        className="grid-2"
        style={{ gridTemplateColumns: "260px 1fr", alignItems: "start" }}
      >
        <aside className="card">
          <h2 className="card-title">{t("standards.listTitle")}</h2>
          {standards.isLoading ? (
            <p className="empty-state">{t("common.loading")}</p>
          ) : (
            <ul className="item-list">
              {items.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedStd(s.id);
                      setSelectedVer(s.versions[0]?.id ?? null);
                    }}
                    className={[
                      "item-row clickable",
                      (current?.id ?? null) === s.id ? "active" : "",
                    ].join(" ")}
                  >
                    <span className="item-name label">{s.code}</span>
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
                        className="btn small danger"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="card" style={{ marginTop: "1rem" }}>
            <h3 className="card-title">{t("standards.createCustom")}</h3>
            <div className="form">
              <input
                placeholder={t("standards.codePlaceholder")}
                value={draftCode}
                onChange={(e) => setDraftCode(e.target.value)}
                className="input mono"
              />
              <input
                placeholder={t("standards.labelPlaceholder")}
                value={draftLabel}
                onChange={(e) => setDraftLabel(e.target.value)}
                className="input"
              />
              <input
                placeholder={t("standards.descPlaceholder", {
                  defaultValue: "Description (optionnelle)",
                })}
                value={draftDescription}
                onChange={(e) => setDraftDescription(e.target.value)}
                className="input"
              />
              <button
                type="button"
                onClick={submitStandard}
                disabled={createStd.isPending || !draftCode || !draftLabel}
                className="btn small primary"
              >
                <Plus size={12} />
                {t("standards.create")}
              </button>
            </div>
          </div>
        </aside>

        <article className="card">
          {current ? (
            <>
              <header className="row">
                <div className="grow">
                  <h2 className="card-title">{current.label}</h2>
                  <p className="card-sub">{current.description}</p>
                </div>
                <span className="badge default">
                  {current.builtin ? t("standards.builtin") : t("standards.custom")}
                </span>
              </header>

              <div className="row">
                {versions.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setSelectedVer(v.id)}
                    className={[
                      "btn small",
                      (activeVersion?.id ?? null) === v.id ? "primary" : "secondary",
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
                      className="input"
                    />
                    <button
                      type="button"
                      onClick={submitVersion}
                      disabled={createVer.isPending || !draftVersion}
                      className="btn small secondary"
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
                    className="btn small danger"
                  >
                    {t("standards.deleteVersion")}
                  </button>
                ) : null}
              </div>

              <section className="card">
                <h3 className="card-title">{t("standards.catalogTitle")}</h3>
                {detail.isLoading ? (
                  <p className="empty-state">{t("common.loading")}</p>
                ) : detail.data && detail.data.catalog.length > 0 ? (
                  <ul className="item-list">
                    {detail.data.catalog.map((c) => (
                      <li key={c.code} className="item-row">
                        <div className="item-main">
                          <p className="row">
                            <span className="item-name label grow">{c.code}</span>
                            <span className="badge default">{c.kind} · {c.severity}</span>
                          </p>
                          <p className="item-name">{c.title}</p>
                          <p className="item-meta">{c.description}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-state">{t("standards.catalogEmpty")}</p>
                )}
              </section>
            </>
          ) : (
            <p className="empty-state">{t("standards.selectStandard")}</p>
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
