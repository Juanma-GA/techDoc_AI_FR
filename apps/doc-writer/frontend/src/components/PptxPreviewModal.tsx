import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  documentsApi,
  sessionsApi,
  type PptxShape,
  type PptxStructureDto,
  type PreviewPptxDto,
  type ZoneDto,
} from "../lib/api";
import { ZonePopover } from "./ZonePopover";

type Props = {
  sessionId: string;
  templateDocId: string;
  defaultFilename?: string;
  onClose: () => void;
};

const XXX_MARKER = /(?<![A-Za-z0-9])[Xx]{3,}(?![A-Za-z0-9])/;
const PLACEHOLDER_MARKER = /\{\{\s*[A-Za-z0-9_.-]+\s*\}\}/;
type Status = "filled" | "empty" | "skipped";

// Modale d'apercu / edition PPTX, pixel-identique au preview (openPptxPreviewModal).
export function PptxPreviewModal({
  sessionId,
  templateDocId,
  defaultFilename,
  onClose,
}: Props) {
  const { t } = useTranslation();

  const previewQuery = useQuery<PreviewPptxDto, ApiClientError>({
    queryKey: ["pptx-preview", sessionId],
    queryFn: () => sessionsApi.previewPptx(sessionId),
  });
  const structureQuery = useQuery<PptxStructureDto, ApiClientError>({
    queryKey: ["pptx-structure", templateDocId],
    queryFn: () => documentsApi.structure(templateDocId),
  });

  const [zones, setZones] = useState<ZoneDto[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectedZid, setSelectedZid] = useState<string | null>(null);
  const [filename, setFilename] = useState(defaultFilename ?? "");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [addTarget, setAddTarget] = useState("");
  const [addLabel, setAddLabel] = useState("");
  // Popover ancre au clic sur une zone du SVG.
  const [popover, setPopover] = useState<{ x: number; y: number; zid: string } | null>(
    null,
  );
  const [popDelArmed, setPopDelArmed] = useState(false);
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const scrollToRow = (zid: string) => {
    const row = rowRefs.current.get(zid);
    if (!row) return;
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    const field = row.querySelector("textarea, input") as HTMLElement | null;
    setTimeout(() => field?.focus(), 250);
  };

  const persistedMeta = useRef<Map<string, { label: string; instruction: string }>>(
    new Map(),
  );
  const initRef = useRef(false);
  useEffect(() => {
    if (initRef.current || !previewQuery.data) return;
    initRef.current = true;
    const z = previewQuery.data.zones ?? [];
    setZones(z);
    setMapping({ ...(previewQuery.data.mapping ?? {}) });
    setSkipped(new Set(z.filter((zz) => zz.active === false).map((zz) => zz.id)));
    persistedMeta.current = new Map(
      z.map((zz) => [zz.id, { label: zz.label ?? "", instruction: zz.instruction ?? "" }]),
    );
  }, [previewQuery.data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const structure = structureQuery.data;
  const slideW = structure?.slide_width_emu ?? 9144000;
  const slideH = structure?.slide_height_emu ?? 6858000;

  const zoneByTarget = useMemo(() => {
    const m: Record<string, ZoneDto> = {};
    for (const z of zones) if (z.target) m[z.target] = z;
    return m;
  }, [zones]);
  const shapeById = useMemo(() => {
    const m: Record<string, PptxShape> = {};
    for (const sl of structure?.slides ?? [])
      for (const sh of sl.shapes ?? []) m[sh.id] = sh;
    return m;
  }, [structure]);

  const statusOf = (zid: string): Status => {
    if (skipped.has(zid)) return "skipped";
    return (mapping[zid] ?? "").trim() ? "filled" : "empty";
  };
  const classify = (sh: PptxShape): string => {
    const z = zoneByTarget[sh.id];
    if (z) return z.kind === "xxx" || z.kind === "placeholder" ? "zone-regex" : "zone-llm";
    const text = sh.text ?? "";
    if (XXX_MARKER.test(text) || PLACEHOLDER_MARKER.test(text)) return "zone-regex";
    return text.trim() ? "label" : "empty";
  };
  const setMap = (zid: string, v: string) =>
    setMapping((p) => ({ ...p, [zid]: v }));
  const applyMapping = (u: Record<string, string>) =>
    setMapping((p) => ({ ...p, ...u }));

  const toggleSkip = async (zid: string) => {
    const willSkip = !skipped.has(zid);
    setSkipped((p) => {
      const n = new Set(p);
      if (willSkip) n.add(zid);
      else n.delete(zid);
      return n;
    });
    try {
      await documentsApi.setZoneActive(templateDocId, zid, !willSkip);
      setZones((p) => p.map((z) => (z.id === zid ? { ...z, active: !willSkip } : z)));
    } catch (e) {
      setSkipped((p) => {
        const n = new Set(p);
        if (willSkip) n.delete(zid);
        else n.add(zid);
        return n;
      });
      setFeedback({ kind: "error", text: (e as Error).message });
    }
  };

  const persistMeta = async (zid: string) => {
    const z = zones.find((zz) => zz.id === zid);
    if (!z) return;
    const prev = persistedMeta.current.get(zid) ?? { label: "", instruction: "" };
    const body: { label?: string; instruction?: string } = {};
    if ((z.label ?? "") !== prev.label) body.label = z.label ?? "";
    if ((z.instruction ?? "") !== prev.instruction) body.instruction = z.instruction ?? "";
    if (Object.keys(body).length === 0) return;
    try {
      await documentsApi.updateZoneMeta(templateDocId, zid, body);
      persistedMeta.current.set(zid, {
        label: z.label ?? "",
        instruction: z.instruction ?? "",
      });
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    }
  };

  const refill = async (zoneIds: string[], force: boolean) => {
    if (zoneIds.length === 0) return;
    setBusy(true);
    setFeedback({ kind: "ok", text: t("pptx.preview.refilling") });
    try {
      for (const zid of zoneIds) await persistMeta(zid);
      const r = await sessionsApi.refillZones(sessionId, { zone_ids: zoneIds, force });
      applyMapping(r.mapping ?? {});
      setFeedback({ kind: "ok", text: t("pptx.preview.refilled", { n: zoneIds.length }) });
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const addZone = async (thenFill: boolean) => {
    if (!addTarget) {
      setFeedback({ kind: "error", text: t("zones.add.targetRequired") });
      return;
    }
    if (!addLabel.trim()) {
      setFeedback({ kind: "error", text: t("zones.add.labelRequired") });
      return;
    }
    const sh = shapeById[addTarget];
    if (!sh) return;
    const idsBefore = new Set(zones.map((z) => z.id));
    setBusy(true);
    try {
      const resp = await documentsApi.addZone(templateDocId, {
        target: addTarget,
        label: addLabel.trim(),
        slide_index: sh.slide_index,
        slide_title: sh.slide_title,
        location: sh.location,
      });
      const newZone = (resp.zones ?? []).find((z) => !idsBefore.has(z.id));
      if (!newZone) {
        setFeedback({ kind: "error", text: t("pptx.preview.noZones") });
        return;
      }
      setZones((p) => [...p, newZone]);
      setMap(newZone.id, "");
      persistedMeta.current.set(newZone.id, {
        label: newZone.label ?? "",
        instruction: newZone.instruction ?? "",
      });
      setAddTarget("");
      setAddLabel("");
      setFeedback({ kind: "ok", text: t("pptx.preview.zoneAdded") });
      if (thenFill) {
        const r = await sessionsApi.refillZones(sessionId, {
          zone_ids: [newZone.id],
          force: true,
        });
        applyMapping(r.mapping ?? {});
        setFeedback({ kind: "ok", text: t("pptx.preview.zoneAddedFilled") });
      }
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const deleteZone = async (zid: string) => {
    try {
      await documentsApi.deleteZone(templateDocId, zid);
      setZones((p) => p.filter((zz) => zz.id !== zid));
      setMapping((p) => {
        const n = { ...p };
        delete n[zid];
        return n;
      });
      setSkipped((p) => {
        const n = new Set(p);
        n.delete(zid);
        return n;
      });
      if (selectedZid === zid) setSelectedZid(null);
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    }
  };

  const bulkSetActive = async (zoneIds: string[], makeActive: boolean) => {
    if (zoneIds.length === 0) return;
    setSkipped((p) => {
      const n = new Set(p);
      for (const zid of zoneIds) {
        if (makeActive) n.delete(zid);
        else n.add(zid);
      }
      return n;
    });
    setZones((p) =>
      p.map((z) => (zoneIds.includes(z.id) ? { ...z, active: makeActive } : z)),
    );
    try {
      await Promise.all(
        zoneIds.map((zid) => documentsApi.setZoneActive(templateDocId, zid, makeActive)),
      );
      setFeedback({
        kind: "ok",
        text: t(makeActive ? "pptx.preview.unskipped" : "pptx.preview.skipped", {
          n: zoneIds.length,
        }),
      });
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    }
  };

  const clearSelected = () => {
    const ids = [...selected];
    if (ids.length === 0) return;
    const u: Record<string, string> = {};
    for (const id of ids) u[id] = "";
    applyMapping(u);
    setFeedback({ kind: "ok", text: t("pptx.preview.cleared", { n: ids.length }) });
  };

  const validate = async () => {
    setBusy(true);
    try {
      await documentsApi.validateZones(templateDocId, true);
      setFeedback({ kind: "ok", text: t("pptx.preview.validated") });
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    setBusy(true);
    setFeedback({ kind: "ok", text: t("pptx.preview.rendering") });
    const finalMapping: Record<string, string> = {};
    for (const z of zones) {
      if (skipped.has(z.id)) {
        if (z.kind === "xxx" || z.kind === "placeholder") finalMapping[z.id] = "";
        continue;
      }
      finalMapping[z.id] = mapping[z.id] ?? "";
    }
    try {
      await sessionsApi.renderPptx(sessionId, finalMapping, filename.trim() || null);
      setFeedback({ kind: "ok", text: t("pptx.preview.downloaded") });
    } catch (e) {
      setFeedback({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const sortedZones = useMemo(
    () =>
      zones.slice().sort((a, b) => {
        const aA = a.active !== false;
        const bA = b.active !== false;
        if (aA !== bA) return aA ? -1 : 1;
        return (
          a.slide_index - b.slide_index ||
          a.location.localeCompare(b.location) ||
          a.id.localeCompare(b.id)
        );
      }),
    [zones],
  );
  const availableShapes = useMemo(() => {
    const used = new Set(zones.map((z) => z.target).filter(Boolean));
    const out: PptxShape[] = [];
    for (const sl of structure?.slides ?? [])
      for (const sh of sl.shapes ?? []) if (!used.has(sh.id)) out.push(sh);
    return out;
  }, [zones, structure]);

  const toggleSelect = (zid: string) =>
    setSelected((p) => {
      const n = new Set(p);
      if (n.has(zid)) n.delete(zid);
      else n.add(zid);
      return n;
    });

  const loading = previewQuery.isLoading || structureQuery.isLoading;
  const loadError = previewQuery.error || structureQuery.error;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-header">
          <h2>{t("pptx.preview.title")}</h2>
          <span className="badge ok">
            {t("pptx.preview.zonesCount", { n: zones.length })}
          </span>
          <button type="button" className="btn ghost small" onClick={onClose}>
            {t("zones.close")}
          </button>
        </div>

        {loading ? (
          <div className="modal-body" style={{ display: "block", textAlign: "center", padding: 40 }}>
            <span className="spinner" /> {t("pptx.preview.loading")}
          </div>
        ) : loadError ? (
          <div className="modal-body" style={{ display: "block" }}>
            <div className="error">{loadError.message}</div>
          </div>
        ) : (
          <div className="modal-body">
            {/* Gauche : apercu */}
            <div>
              <small style={{ display: "block", color: "var(--fg-dim)", fontSize: "0.78rem", marginBottom: 6 }}>
                {t("pptx.preview.legend")}
              </small>
              <div className="slides-preview">
                {(structure?.slides ?? []).map((slide) => {
                  const shapes = (slide.shapes ?? []).filter((sh) => sh.bbox);
                  return (
                    <div className="slide-preview" key={slide.index}>
                      <div className="slide-preview-title">
                        Slide {slide.index}
                        {slide.title ? ` - ${slide.title}` : ""}
                      </div>
                      <div className="slide-canvas">
                        <svg
                          className="slide-svg"
                          viewBox={`0 0 ${slideW} ${slideH}`}
                          preserveAspectRatio="xMidYMid meet"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          {shapes.map((sh) => {
                            const z = zoneByTarget[sh.id];
                            const sel = z && z.id === selectedZid ? " selected" : "";
                            const sk = z && skipped.has(z.id) ? " skipped" : "";
                            const b = sh.bbox!;
                            return (
                              <g
                                className={`shape ${classify(sh)}${sel}${sk}`}
                                key={sh.id}
                                onClick={(e) => {
                                  if (z) {
                                    setSelectedZid(z.id);
                                    setPopDelArmed(false);
                                    setPopover({ x: e.clientX, y: e.clientY, zid: z.id });
                                  } else {
                                    setAddTarget(sh.id);
                                  }
                                }}
                              >
                                <rect x={b.left} y={b.top} width={b.width} height={b.height} />
                              </g>
                            );
                          })}
                        </svg>
                        <div className="shape-overlays">
                          {shapes.map((sh) => {
                            const z = zoneByTarget[sh.id];
                            const b = sh.bbox!;
                            const text = z
                              ? mapping[z.id] ?? ""
                              : (sh.text ?? "").replace(/\s+/g, " ").trim();
                            if (!text && !z) return null;
                            const sk = z && skipped.has(z.id) ? " skipped" : "";
                            const empty = z && !(mapping[z.id] ?? "").trim() ? " preview-empty" : "";
                            return (
                              <div
                                className={`shape-overlay ${classify(sh)}${sk}${empty}`}
                                key={sh.id}
                                style={{
                                  left: `${(b.left / slideW) * 100}%`,
                                  top: `${(b.top / slideH) * 100}%`,
                                  width: `${(b.width / slideW) * 100}%`,
                                  height: `${(b.height / slideH) * 100}%`,
                                }}
                              >
                                {text}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Droite : edition */}
            <div>
              <h3 style={{ marginTop: 0, fontFamily: "var(--font-display)", fontSize: "0.9rem" }}>
                {t("pptx.preview.editTitle")}
              </h3>
              <small style={{ display: "block", color: "var(--fg-dim)", fontSize: "0.78rem", marginBottom: 8 }}>
                {t("pptx.preview.editHint")}
              </small>

              {sortedZones.length === 0 ? (
                <div className="empty-state">{t("pptx.preview.noZones")}</div>
              ) : (
                <>
                  <label className="checkbox" style={{ fontSize: "0.78rem", marginBottom: 6 }}>
                    <input
                      type="checkbox"
                      checked={sortedZones.length > 0 && selected.size === sortedZones.length}
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? new Set(sortedZones.map((z) => z.id))
                            : new Set(),
                        )
                      }
                    />
                    <span>{t("zones.bulk.selectAll")}</span>
                  </label>
                  <div className={`bulk-toolbar${selected.size > 0 ? " visible" : ""}`}>
                    <span style={{ fontSize: "0.85rem" }}>
                      {t("zones.bulk.count", { n: selected.size })}
                    </span>
                    <button type="button" className="btn secondary small" disabled={busy} onClick={() => refill([...selected], false)}>
                      {t("pptx.preview.refill")}
                    </button>
                    <button type="button" className="btn secondary small" disabled={busy} onClick={() => refill([...selected], true)}>
                      {t("pptx.preview.force")}
                    </button>
                    <button type="button" className="btn ghost small" disabled={busy} onClick={() => bulkSetActive([...selected], false)}>
                      {t("pptx.preview.skipSel")}
                    </button>
                    <button type="button" className="btn ghost small" disabled={busy} onClick={() => bulkSetActive([...selected], true)}>
                      {t("pptx.preview.unskipSel")}
                    </button>
                    <button type="button" className="btn ghost small" disabled={busy} onClick={clearSelected}>
                      {t("pptx.preview.clear")}
                    </button>
                  </div>
                  <small style={{ display: "block", color: "var(--fg-dim)", fontSize: "0.78rem", margin: "4px 0 8px" }}>
                    {t("pptx.preview.metaHint")}
                  </small>

                  <div className="zones-edit-list">
                    {sortedZones.map((z) => {
                      const st = statusOf(z.id);
                      return (
                        <div
                          className={`zone-edit${st === "skipped" ? " skipped" : ""}`}
                          key={z.id}
                          ref={(el) => {
                            if (el) rowRefs.current.set(z.id, el);
                            else rowRefs.current.delete(z.id);
                          }}
                          onClick={() => setSelectedZid(z.id)}
                        >
                          <div className="row" style={{ gap: 8, alignItems: "flex-start" }}>
                            <input
                              type="checkbox"
                              checked={selected.has(z.id)}
                              onClick={(e) => e.stopPropagation()}
                              onChange={() => toggleSelect(z.id)}
                              style={{ marginTop: 4 }}
                            />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div className="zone-edit-meta">
                                <span>
                                  {z.location || `Slide ${z.slide_index}`} - {z.kind}
                                </span>
                                <span className={`zone-status ${st}`}>
                                  {t(`pptx.preview.status.${st}`)}
                                </span>
                                <button
                                  type="button"
                                  className="btn secondary small"
                                  style={{ marginLeft: "auto", padding: "2px 8px", fontSize: "0.7rem" }}
                                  disabled={busy}
                                  title={t("pptx.preview.zoneIaHint")}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    refill([z.id], false);
                                  }}
                                >
                                  {t("pptx.preview.zoneIa")}
                                </button>
                                <button
                                  type="button"
                                  className="btn ghost small"
                                  style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleSkip(z.id);
                                  }}
                                >
                                  {skipped.has(z.id)
                                    ? t("pptx.preview.reintegrate")
                                    : t("pptx.preview.skip")}
                                </button>
                                <button
                                  type="button"
                                  className="btn ghost small"
                                  style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                                  title={t("pptx.preview.deleteZoneHint")}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    deleteZone(z.id);
                                  }}
                                >
                                  {t("pptx.preview.deleteZone")}
                                </button>
                              </div>
                              <div className="label" style={{ margin: "4px 0 2px" }}>
                                {t("zones.col.label")}
                              </div>
                              <input
                                className="input"
                                type="text"
                                value={z.label ?? ""}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) =>
                                  setZones((p) =>
                                    p.map((zz) =>
                                      zz.id === z.id ? { ...zz, label: e.target.value } : zz,
                                    ),
                                  )
                                }
                                onBlur={() => void persistMeta(z.id)}
                              />
                              <div className="label" style={{ margin: "6px 0 2px" }}>
                                {t("zones.col.instruction")}
                              </div>
                              <textarea
                                className="input"
                                rows={2}
                                value={z.instruction ?? ""}
                                placeholder={t("zones.col.instructionPlaceholder")}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) =>
                                  setZones((p) =>
                                    p.map((zz) =>
                                      zz.id === z.id
                                        ? { ...zz, instruction: e.target.value }
                                        : zz,
                                    ),
                                  )
                                }
                                onBlur={() => void persistMeta(z.id)}
                              />
                              <div className="label" style={{ margin: "6px 0 2px" }}>
                                {t("pptx.preview.content")}
                              </div>
                              <textarea
                                rows={3}
                                value={mapping[z.id] ?? ""}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => setMap(z.id, e.target.value)}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {/* Ajouter une zone */}
              <div className="card" style={{ marginTop: 10, background: "var(--bg-2)" }}>
                <h3 style={{ margin: "0 0 8px 0", fontFamily: "var(--font-display)", fontSize: "0.85rem" }}>
                  {t("pptx.preview.addZoneTitle")}
                </h3>
                <small style={{ display: "block", color: "var(--fg-dim)", fontSize: "0.78rem", marginBottom: 8 }}>
                  {t("pptx.preview.addZoneHint")}
                </small>
                <div className="form">
                  <label>
                    <div className="label">{t("zones.col.target")}</div>
                    <select
                      className="input"
                      value={addTarget}
                      onChange={(e) => setAddTarget(e.target.value)}
                    >
                      <option value="">--</option>
                      {availableShapes.map((s) => {
                        const prev = (s.text ?? "").replace(/\s+/g, " ").slice(0, 60);
                        return (
                          <option key={s.id} value={s.id}>
                            Slide {s.slide_index} - {s.kind}
                            {prev ? ` ("${prev}")` : ""}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                  <label>
                    <div className="label">{t("zones.col.label")}</div>
                    <input
                      className="input"
                      type="text"
                      value={addLabel}
                      placeholder={t("zones.addPlaceholder")}
                      onChange={(e) => setAddLabel(e.target.value)}
                    />
                  </label>
                  <div className="row" style={{ gap: 6 }}>
                    <button type="button" className="btn primary small" disabled={busy} onClick={() => addZone(false)}>
                      {t("pptx.preview.addZone")}
                    </button>
                    <button
                      type="button"
                      className="btn secondary small"
                      disabled={busy}
                      title={t("pptx.preview.addFillHint")}
                      onClick={() => addZone(true)}
                    >
                      {t("pptx.preview.addAndFill")}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="modal-footer">
          <label style={{ flex: 1, minWidth: 240 }}>
            <div className="label">{t("generate.filename")}</div>
            <input
              className="input"
              type="text"
              value={filename}
              placeholder={t("generate.filenamePlaceholder")}
              onChange={(e) => setFilename(e.target.value)}
            />
          </label>
          {feedback ? (
            <span className="grow">
              <span className={feedback.kind === "ok" ? "success" : "error"}>
                {feedback.text}
              </span>
            </span>
          ) : (
            <span className="grow" />
          )}
          <button
            type="button"
            className="btn secondary"
            disabled={busy}
            title={t("pptx.preview.validateHint")}
            onClick={validate}
          >
            {t("pptx.preview.validate")}
          </button>
          <button type="button" className="btn primary" disabled={busy || loading} onClick={download}>
            {t("pptx.preview.download")}
          </button>
        </div>
      </div>

      {popover
        ? (() => {
            const z = zones.find((zz) => zz.id === popover.zid);
            if (!z) return null;
            return (
              <ZonePopover
                x={popover.x}
                y={popover.y}
                meta={`${z.location || `Slide ${z.slide_index}`} - ${z.kind} · ${t(
                  `pptx.preview.status.${statusOf(z.id)}`,
                )}`}
                label={z.label || "-"}
                onClose={() => setPopover(null)}
              >
                <button
                  type="button"
                  className="btn primary small"
                  onClick={() => {
                    toggleSkip(z.id);
                    setPopover(null);
                  }}
                >
                  {skipped.has(z.id)
                    ? t("pptx.preview.reintegrate")
                    : t("pptx.preview.skip")}
                </button>
                <button
                  type="button"
                  className="btn secondary small"
                  onClick={() => {
                    scrollToRow(z.id);
                    setPopover(null);
                  }}
                >
                  {t("pptx.preview.popover.edit")}
                </button>
                <button
                  type="button"
                  className={`btn small ${popDelArmed ? "danger" : "ghost"}`}
                  onClick={() => {
                    if (!popDelArmed) {
                      setPopDelArmed(true);
                      return;
                    }
                    deleteZone(z.id);
                    setPopover(null);
                  }}
                >
                  {popDelArmed ? t("data.confirmAgain") : t("pptx.preview.popover.delete")}
                </button>
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => setPopover(null)}
                >
                  {t("zones.close")}
                </button>
              </ZonePopover>
            );
          })()
        : null}
    </div>
  );
}
