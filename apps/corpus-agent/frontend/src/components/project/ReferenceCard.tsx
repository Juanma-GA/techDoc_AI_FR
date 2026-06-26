import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { FileDropzone } from "@internal/ui";

import { referenceApi } from "../../lib/api";
import type { ReferenceOut, SheetColumnOut, SheetPreviewOut } from "../../lib/types";

type Row = { name: string; sheet: string; column: string; builtin: boolean };

export function ReferenceCard({ pid }: { pid: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const refQuery = useQuery<ReferenceOut>({ queryKey: ["reference", pid], queryFn: () => referenceApi.get(pid) });
  const baslQuery = useQuery<ReferenceOut>({ queryKey: ["basl", pid], queryFn: () => referenceApi.basl(pid) });

  const [rows, setRows] = useState<Row[]>([]);
  const [headerRows, setHeaderRows] = useState<Record<string, number>>({});
  const [columns, setColumns] = useState<Record<string, SheetColumnOut[]>>({});
  const [preview, setPreview] = useState<Record<string, SheetPreviewOut>>({});
  const [feedback, setFeedback] = useState<string | null>(null);
  // BASL : même éditeur de mapping que le référentiel (état parallèle).
  const [baslRows, setBaslRows] = useState<Row[]>([]);
  const [baslHeaderRows, setBaslHeaderRows] = useState<Record<string, number>>({});
  const [baslColumns, setBaslColumns] = useState<Record<string, SheetColumnOut[]>>({});
  const [baslPreview, setBaslPreview] = useState<Record<string, SheetPreviewOut>>({});
  const [baslMsg, setBaslMsg] = useState<string | null>(null);

  const ref = refQuery.data;
  useEffect(() => {
    if (ref) {
      setRows(ref.columns.map((c) => ({ name: c.name, sheet: c.sheet, column: c.column, builtin: c.builtin })));
      setHeaderRows(ref.header_rows ?? {});
    }
  }, [ref]);

  const loadColumns = async (sheet: string) => {
    if (!sheet || columns[`${sheet}:${headerRows[sheet] ?? 0}`]) return;
    const cols = await referenceApi.columns(pid, sheet, headerRows[sheet]);
    setColumns((prev) => ({ ...prev, [`${sheet}:${headerRows[sheet] ?? 0}`]: cols }));
  };
  const loadPreview = async (sheet: string) => {
    if (!sheet || preview[sheet]) return;
    const data = await referenceApi.preview(pid, sheet);
    setPreview((prev) => ({ ...prev, [sheet]: data }));
  };
  const loadBaslColumns = async (sheet: string) => {
    if (!sheet || baslColumns[`${sheet}:${baslHeaderRows[sheet] ?? 0}`]) return;
    const cols = await referenceApi.baslColumns(pid, sheet, baslHeaderRows[sheet]);
    setBaslColumns((prev) => ({ ...prev, [`${sheet}:${baslHeaderRows[sheet] ?? 0}`]: cols }));
  };
  const loadBaslPreview = async (sheet: string) => {
    if (!sheet || baslPreview[sheet]) return;
    const data = await referenceApi.baslPreview(pid, sheet);
    setBaslPreview((prev) => ({ ...prev, [sheet]: data }));
  };

  // Charge l'aperçu (et les colonnes) des onglets déjà mappés dès le chargement
  // du référentiel : sans ça, le tableau d'aperçu — qui sert à désigner la
  // ligne d'en-tête — ne s'affiche qu'après avoir rouvert un menu « Onglet ».
  // On le ré-exécute quand une ligne d'en-tête change pour rafraîchir les
  // colonnes alignées sur la nouvelle ligne.
  useEffect(() => {
    if (!ref?.path) return;
    const selected = [...new Set(ref.columns.map((c) => c.sheet).filter(Boolean))];
    for (const s of selected) {
      void loadPreview(s);
      void loadColumns(s);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, headerRows]);

  // BASL : même éditeur de mapping que le référentiel. On hydrate le registre
  // de colonnes et les lignes d'en-tête persistés dès que la BASL est chargée.
  const basl = baslQuery.data;
  useEffect(() => {
    if (basl) {
      setBaslRows(basl.columns.map((c) => ({ name: c.name, sheet: c.sheet, column: c.column, builtin: c.builtin })));
      setBaslHeaderRows(basl.header_rows ?? {});
    }
  }, [basl]);

  // Charge aperçu + colonnes des onglets déjà mappés de la BASL (cf. note du
  // référentiel) ; ré-exécuté quand une ligne d'en-tête BASL change.
  useEffect(() => {
    if (!basl?.path) return;
    const selected = [...new Set(basl.columns.map((c) => c.sheet).filter(Boolean))];
    for (const s of selected) {
      void loadBaslPreview(s);
      void loadBaslColumns(s);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basl, baslHeaderRows]);

  const upload = useMutation({
    mutationFn: (file: File) => referenceApi.upload(pid, file),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["reference", pid] }),
  });
  const uploadBasl = useMutation({
    mutationFn: (file: File) => referenceApi.uploadBasl(pid, file),
    onSuccess: () => {
      setBaslMsg(t("referentiel.baslSaved"));
      void qc.invalidateQueries({ queryKey: ["basl", pid] });
    },
  });
  const saveBasl = useMutation({
    mutationFn: () =>
      referenceApi.saveBaslMapping(pid, {
        columns: baslRows.map((r) => ({ name: r.name, sheet: r.sheet, column: r.column })),
        header_rows: baslHeaderRows,
      }),
    onSuccess: () => {
      setBaslMsg(t("referentiel.baslMappingSaved"));
      void qc.invalidateQueries({ queryKey: ["basl", pid] });
    },
  });
  const save = useMutation({
    mutationFn: () =>
      referenceApi.saveMapping(pid, {
        columns: rows.map((r) => ({ name: r.name, sheet: r.sheet, column: r.column })),
        header_rows: headerRows,
      }),
    onSuccess: () => {
      setFeedback(t("referentiel.mappingSaved"));
      void qc.invalidateQueries({ queryKey: ["reference", pid] });
    },
  });

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const setBaslRow = (i: number, patch: Partial<Row>) =>
    setBaslRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const sheets = ref?.sheets ?? [];
  const baslSheets = basl?.sheets ?? [];

  return (
    <div className="card">
      <h2 className="card-title">{t("referentiel.atmTitle")}</h2>
      <div className="banner">{t("settings.atmColumnsMoved")}</div>

      <FileDropzone
        onFiles={(fs) => fs[0] && upload.mutate(fs[0])}
        accept=".xlsx,.xlsm"
        label={t("referentiel.upload")}
      />
      <div className="label" style={{ marginTop: 8 }}>
        {upload.isPending
          ? t("common.loading")
          : ref?.path
            ? `${t("referentiel.loaded")} — ${sheets.join(", ")}`
            : t("referentiel.none")}
      </div>
      {upload.isError && <div className="error">{(upload.error as Error).message}</div>}

      {ref?.path && (
        <>
          <div className="label" style={{ margin: "12px 0 6px" }}>{t("referentiel.mappingHint")}</div>
          {rows.length > 0 && (
            <div className="ref-row" style={{ marginBottom: 4 }}>
              <span className="label">{t("referentiel.hdrName")}</span>
              <span className="label">{t("referentiel.hdrSheet")}</span>
              <span className="label">{t("referentiel.hdrColumn")}</span>
              <span />
            </div>
          )}
          {rows.map((r, i) => {
            const colKey = `${r.sheet}:${headerRows[r.sheet] ?? 0}`;
            const cols = columns[colKey] ?? [];
            return (
              <div className="ref-row" key={i}>
                <input
                  className="input"
                  value={r.name}
                  readOnly={r.builtin}
                  placeholder={t("referentiel.namePh")}
                  onChange={(e) => setRow(i, { name: e.target.value })}
                />
                <select
                  value={r.sheet}
                  onChange={(e) => {
                    setRow(i, { sheet: e.target.value, column: "" });
                    void loadColumns(e.target.value);
                    void loadPreview(e.target.value);
                  }}
                  onFocus={() => void loadColumns(r.sheet)}
                >
                  <option value="">—</option>
                  {sheets.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <select value={r.column} onChange={(e) => setRow(i, { column: e.target.value })} onFocus={() => void loadColumns(r.sheet)}>
                  <option value="">{r.column || "—"}</option>
                  {cols.map((c) => (
                    <option key={c.letter} value={c.letter}>{c.letter} · {c.header}</option>
                  ))}
                </select>
                {r.builtin ? (
                  <span />
                ) : (
                  <button type="button" className="btn ghost small" onClick={() => setRows((p) => p.filter((_, idx) => idx !== i))}>
                    ×
                  </button>
                )}
              </div>
            );
          })}

          {sheets.some((s) => preview[s]) && (
            <div className="label" style={{ margin: "12px 0 6px" }}>{t("referentiel.headerRowHint")}</div>
          )}
          {sheets.map((s) =>
            preview[s] ? (
              <table className="hdr-preview" key={s}>
                <tbody>
                  {preview[s].rows.map((cells, ri) => (
                    <tr
                      key={ri}
                      className={`hdr-row${headerRows[s] === ri + 1 ? " active" : ""}`}
                      onClick={() => setHeaderRows((prev) => ({ ...prev, [s]: ri + 1 }))}
                    >
                      <td className="hdr-rownum">{ri + 1}</td>
                      {cells.map((c, ci) => (
                        <td key={ci}>{c}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null,
          )}

          <div className="row" style={{ marginTop: 10 }}>
            <button type="button" className="btn secondary small" onClick={() => setRows((p) => [...p, { name: "", sheet: "", column: "", builtin: false }])}>
              {t("referentiel.addColumn")}
            </button>
            <button type="button" className="btn primary small" onClick={() => save.mutate()} disabled={save.isPending}>
              {t("referentiel.saveMapping")}
            </button>
            {feedback && <span className="success">{feedback}</span>}
          </div>
        </>
      )}

      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "16px 0" }} />
      <div className="label" style={{ margin: "0 0 4px" }}>{t("referentiel.baslTitle")}</div>
      <FileDropzone
        onFiles={(fs) => {
          if (fs[0]) {
            setBaslMsg(null);
            uploadBasl.mutate(fs[0]);
          }
        }}
        accept=".xlsx,.xlsm"
        label="BASL"
      />
      <div className="label" style={{ marginTop: 8 }}>
        {uploadBasl.isPending
          ? t("common.loading")
          : basl?.path
            ? `${t("referentiel.loaded")} — ${baslSheets.join(", ")}`
            : t("referentiel.baslNone")}
      </div>
      {uploadBasl.isError && <div className="error">{(uploadBasl.error as Error).message}</div>}

      {basl?.path && (
        <>
          <div className="label" style={{ margin: "12px 0 6px" }}>{t("referentiel.baslMappingHint")}</div>
          {baslRows.length > 0 && (
            <div className="ref-row" style={{ marginBottom: 4 }}>
              <span className="label">{t("referentiel.hdrName")}</span>
              <span className="label">{t("referentiel.hdrSheet")}</span>
              <span className="label">{t("referentiel.hdrColumn")}</span>
              <span />
            </div>
          )}
          {baslRows.map((r, i) => {
            const colKey = `${r.sheet}:${baslHeaderRows[r.sheet] ?? 0}`;
            const cols = baslColumns[colKey] ?? [];
            return (
              <div className="ref-row" key={i}>
                <input
                  className="input"
                  value={r.name}
                  readOnly={r.builtin}
                  placeholder={t("referentiel.namePh")}
                  onChange={(e) => setBaslRow(i, { name: e.target.value })}
                />
                <select
                  value={r.sheet}
                  onChange={(e) => {
                    setBaslRow(i, { sheet: e.target.value, column: "" });
                    void loadBaslColumns(e.target.value);
                    void loadBaslPreview(e.target.value);
                  }}
                  onFocus={() => void loadBaslColumns(r.sheet)}
                >
                  <option value="">—</option>
                  {baslSheets.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <select value={r.column} onChange={(e) => setBaslRow(i, { column: e.target.value })} onFocus={() => void loadBaslColumns(r.sheet)}>
                  <option value="">{r.column || "—"}</option>
                  {cols.map((c) => (
                    <option key={c.letter} value={c.letter}>{c.letter} · {c.header}</option>
                  ))}
                </select>
                {r.builtin ? (
                  <span />
                ) : (
                  <button type="button" className="btn ghost small" onClick={() => setBaslRows((p) => p.filter((_, idx) => idx !== i))}>
                    ×
                  </button>
                )}
              </div>
            );
          })}

          {baslSheets.some((s) => baslPreview[s]) && (
            <div className="label" style={{ margin: "12px 0 6px" }}>{t("referentiel.headerRowHint")}</div>
          )}
          {baslSheets.map((s) =>
            baslPreview[s] ? (
              <table className="hdr-preview" key={s}>
                <tbody>
                  {baslPreview[s].rows.map((cells, ri) => (
                    <tr
                      key={ri}
                      className={`hdr-row${baslHeaderRows[s] === ri + 1 ? " active" : ""}`}
                      onClick={() => setBaslHeaderRows((prev) => ({ ...prev, [s]: ri + 1 }))}
                    >
                      <td className="hdr-rownum">{ri + 1}</td>
                      {cells.map((c, ci) => (
                        <td key={ci}>{c}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null,
          )}

          <div className="row" style={{ marginTop: 10 }}>
            <button type="button" className="btn secondary small" onClick={() => setBaslRows((p) => [...p, { name: "", sheet: "", column: "", builtin: false }])}>
              {t("referentiel.addColumn")}
            </button>
            <button type="button" className="btn primary small" onClick={() => saveBasl.mutate()} disabled={saveBasl.isPending}>
              {t("referentiel.saveMapping")}
            </button>
            {baslMsg && !uploadBasl.isPending && <span className="success">{baslMsg}</span>}
          </div>
        </>
      )}
    </div>
  );
}
