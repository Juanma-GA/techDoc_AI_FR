import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { exportUrl, qcApi, type QcChecklistDto, type QcItemDto } from "../lib/api";

const STATUS_VALUES = ["ok", "ko", "na"] as const;

export function Qc() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [title, setTitle] = useState(t("qc.defaultTitle"));
  const [openId, setOpenId] = useState<string | null>(null);

  const listQuery = useQuery<QcChecklistDto[]>({ queryKey: ["qc"], queryFn: qcApi.list });
  const lists = listQuery.data ?? [];

  // Ouvre la premiere checklist par defaut, comme le preview.
  useEffect(() => {
    if (openId === null && lists.length) setOpenId(lists[0]!.id);
  }, [lists, openId]);

  const createMutation = useMutation({
    mutationFn: () => qcApi.create({ title: title.trim(), template: "assembly" }),
    onSuccess: (cl) => {
      setOpenId(cl.id);
      void qc.invalidateQueries({ queryKey: ["qc"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => qcApi.remove(id),
    onSuccess: (_d, id) => {
      if (openId === id) setOpenId(null);
      void qc.invalidateQueries({ queryKey: ["qc"] });
    },
  });

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <article className="card">
        <h2 className="card-title">{t("qc.title")}</h2>
        <p className="banner info">{t("qc.banner")}</p>
        <div className="row">
          <input
            className="input grow"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("qc.titlePlaceholder")}
          />
          <button
            type="button"
            className="btn primary"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? <span className="spinner" /> : null}
            <span>{t("qc.newChecklist")}</span>
          </button>
        </div>

        {lists.length ? (
          <div className="row" style={{ flexWrap: "wrap", marginTop: 12 }}>
            {lists.map((c) => (
              <div key={c.id} className="row" style={{ gap: 4 }}>
                <button type="button" className="btn secondary small" onClick={() => setOpenId(c.id)}>
                  {c.title} ({t("qc.progress", { done: c.summary.done, total: c.summary.total })})
                </button>
                <button
                  type="button"
                  className="btn danger small"
                  onClick={() => deleteMutation.mutate(c.id)}
                  disabled={deleteMutation.isPending}
                >
                  x
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </article>

      {openId ? <QcDetail key={openId} checklistId={openId} /> : null}
    </div>
  );
}

function QcDetail({ checklistId }: { checklistId: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const detailQuery = useQuery<QcChecklistDto>({
    queryKey: ["qc", checklistId],
    queryFn: () => qcApi.get(checklistId),
  });

  const statusMutation = useMutation({
    mutationFn: ({ itemId, status }: { itemId: string; status: string }) =>
      qcApi.setItem(itemId, { status }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["qc", checklistId] });
      void qc.invalidateQueries({ queryKey: ["qc"] });
    },
  });

  if (detailQuery.isLoading) return <span className="spinner" />;
  if (detailQuery.isError || !detailQuery.data) {
    return (
      <article className="card">
        <div className="empty-state">
          <h3 className="card-title">
            {detailQuery.error instanceof Error ? detailQuery.error.message : t("qc.empty")}
          </h3>
        </div>
      </article>
    );
  }

  const cl = detailQuery.data;
  const s = cl.summary;

  return (
    <article className="card">
      <h2 className="card-title">
        <span className="row" style={{ flexWrap: "wrap" }}>
          <span className="grow">{cl.title}</span>
          <span className="badge ok">{t("qc.okCount", { count: s.ok })}</span>
          <span className="badge danger">{t("qc.koCount", { count: s.ko })}</span>
          <span className="badge default">{t("qc.naCount", { count: s.na })}</span>
          <span className="badge info">{t("qc.progress", { done: s.done, total: s.total })}</span>
          <a href={exportUrl.qcCsv(cl.id)}>
            <button type="button" className="btn secondary small">
              {t("common.exportCsv")}
            </button>
          </a>
        </span>
      </h2>
      <ul className="item-list">
        {cl.items.map((item) => (
          <li key={item.id} className="item-row">
            <div className="row" style={{ flexWrap: "wrap" }}>
              <span className="badge default">{item.category || t("qc.noCategory")}</span>
              <span className="grow">{item.label}</span>
              {STATUS_VALUES.map((val) => (
                <button
                  key={val}
                  type="button"
                  className={`btn ${item.status === val ? "primary" : "ghost"} small`}
                  onClick={() => statusMutation.mutate({ itemId: item.id, status: val })}
                >
                  {t(`qc.${val}`)}
                </button>
              ))}
            </div>
            <QcComment item={item} checklistId={checklistId} />
          </li>
        ))}
      </ul>
    </article>
  );
}

function QcComment({ item, checklistId }: { item: QcItemDto; checklistId: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [value, setValue] = useState(item.comment);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Resynchronise si le serveur renvoie une valeur differente (ex. refetch).
  useEffect(() => {
    setValue(item.comment);
  }, [item.comment]);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const commentMutation = useMutation({
    mutationFn: (comment: string) => qcApi.setItem(item.id, { comment }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["qc", checklistId] }),
  });

  function handleChange(next: string) {
    setValue(next);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      commentMutation.mutate(next);
    }, 500);
  }

  return (
    <input
      className="input"
      style={{ marginTop: 8 }}
      value={value}
      onChange={(e) => handleChange(e.target.value)}
      placeholder={t("qc.commentPlaceholder")}
    />
  );
}
