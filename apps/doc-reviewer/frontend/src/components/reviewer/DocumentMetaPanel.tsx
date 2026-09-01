import { Settings2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { usePatchDocumentMeta } from "../../hooks/useDocuments";
import type { Document } from "../../types/domain";

type Props = {
  document: Document;
};

/**
 * Mapping manuel par document : champs libres references par les consignes
 * de checklist (« verifier que la date de revision correspond… »). Saisis une
 * fois par document, injectes dans le contexte du scan IA cote backend
 * (cf. `rules_engine._doc_meta_block`).
 */
export function DocumentMetaPanel({ document }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const patch = usePatchDocumentMeta(document.id);

  const [revisionDate, setRevisionDate] = useState(document.meta_revision_date ?? "");
  const [cmmNumber, setCmmNumber] = useState(document.meta_cmm_number ?? "");
  const [firstIssueDate, setFirstIssueDate] = useState(document.meta_first_issue_date ?? "");
  const [revisionNumber, setRevisionNumber] = useState(document.meta_revision_number ?? "");

  useEffect(() => {
    setRevisionDate(document.meta_revision_date ?? "");
    setCmmNumber(document.meta_cmm_number ?? "");
    setFirstIssueDate(document.meta_first_issue_date ?? "");
    setRevisionNumber(document.meta_revision_number ?? "");
  }, [document]);

  function save(): void {
    patch.mutate({
      meta_revision_date: revisionDate || null,
      meta_cmm_number: cmmNumber || null,
      meta_first_issue_date: firstIssueDate || null,
      meta_revision_number: revisionNumber || null,
    });
  }

  if (!open) {
    return (
      <button type="button" className="btn ghost small" onClick={() => setOpen(true)}>
        <Settings2 size={14} />
        {t("reviewer.meta.toggle")}
      </button>
    );
  }

  return (
    <div className="card" style={{ position: "fixed", top: 52, right: 16, zIndex: 20, width: 320 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div className="card-title" style={{ margin: 0 }}>
          {t("reviewer.meta.title")}
        </div>
        <button type="button" className="btn ghost small" onClick={() => setOpen(false)} aria-label={t("common.close")}>
          <X size={14} />
        </button>
      </div>
      <p className="card-sub">{t("reviewer.meta.subtitle")}</p>

      <label className="label">
        {t("reviewer.meta.revisionDate")}
        <input
          className="input"
          value={revisionDate}
          onChange={(e) => setRevisionDate(e.target.value)}
          onBlur={save}
          placeholder={t("reviewer.meta.revisionDatePlaceholder")}
        />
      </label>
      <label className="label">
        {t("reviewer.meta.cmmNumber")}
        <input
          className="input"
          value={cmmNumber}
          onChange={(e) => setCmmNumber(e.target.value)}
          onBlur={save}
          placeholder={t("reviewer.meta.cmmNumberPlaceholder")}
        />
      </label>
      <label className="label">
        {t("reviewer.meta.firstIssueDate")}
        <input
          className="input"
          value={firstIssueDate}
          onChange={(e) => setFirstIssueDate(e.target.value)}
          onBlur={save}
          placeholder={t("reviewer.meta.firstIssueDatePlaceholder")}
        />
      </label>
      <label className="label">
        {t("reviewer.meta.revisionNumber")}
        <input
          className="input"
          value={revisionNumber}
          onChange={(e) => setRevisionNumber(e.target.value)}
          onBlur={save}
          placeholder={t("reviewer.meta.revisionNumberPlaceholder")}
        />
      </label>
    </div>
  );
}
