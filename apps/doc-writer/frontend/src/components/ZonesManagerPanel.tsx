import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  documentsApi,
  type FlowDto,
  type PptxShape,
  type PptxStructureDto,
  type ZoneDto,
  type ZonesDto,
} from "../lib/api";
import { DocFlowPreview } from "./DocFlowPreview";
import { ZonePopover } from "./ZonePopover";

type Props = { docId: string; filename: string; onClose: () => void };

// Gestionnaire de zones complet, pixel-identique au preview (renderZonesManager).
export function ZonesManagerPanel({ docId, filename, onClose }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const zonesKey = ["documents", docId, "zones"];

  const zonesQuery = useQuery<ZonesDto, ApiClientError>({
    queryKey: zonesKey,
    queryFn: () => documentsApi.zones(docId),
  });
  const structureQuery = useQuery<PptxStructureDto, ApiClientError>({
    queryKey: ["documents", docId, "structure"],
    queryFn: () => documentsApi.structure(docId),
  });
  // Apercu 'flux document' (Word/PDF) : charge seulement quand la structure n'a
  // pas de geometrie (sinon c'est un PPTX -> apercu SVG positionne).
  const hasGeometry = (structureQuery.data?.slide_width_emu ?? 0) > 0;
  const flowQuery = useQuery<FlowDto, ApiClientError>({
    queryKey: ["documents", docId, "flow"],
    queryFn: () => documentsApi.flow(docId),
    enabled: structureQuery.isSuccess && !hasGeometry,
  });

  const [edits, setEdits] = useState<
    Record<string, { label: string; instruction: string }>
  >({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [kindFilter, setKindFilter] = useState("");
  const [addTarget, setAddTarget] = useState("");
  const [addLabel, setAddLabel] = useState("");
  const [feedback, setFeedback] = useState<
    { kind: "ok" | "error"; text: string } | null
  >(null);
  const [bulkArmed, setBulkArmed] = useState(false);
  const [delArmed, setDelArmed] = useState<string | null>(null);
  // Popover ancre au clic sur une zone du SVG (Editer / Supprimer / Fermer).
  const [popover, setPopover] = useState<{ x: number; y: number; zid: string } | null>(
    null,
  );
  const [popDelArmed, setPopDelArmed] = useState(false);
  const rowRefs = useRef<Map<string, HTMLTableRowElement>>(new Map());

  const onData = (d: ZonesDto) => qc.setQueryData(zonesKey, d);
  const onErr = (e: ApiClientError) => setFeedback({ kind: "error", text: e.message });

  const saveMut = useMutation({
    mutationFn: (v: { zid: string; label: string; instruction: string }) =>
      documentsApi.updateZoneMeta(docId, v.zid, {
        label: v.label,
        instruction: v.instruction,
      }),
    onSuccess: (d, v) => {
      onData(d);
      setEdits((p) => {
        const n = { ...p };
        delete n[v.zid];
        return n;
      });
      setFeedback({ kind: "ok", text: t("zones.saved") });
    },
    onError: onErr,
  });
  const deleteMut = useMutation({
    mutationFn: (zid: string) => documentsApi.deleteZone(docId, zid),
    onSuccess: onData,
    onError: onErr,
  });
  const restoreMut = useMutation({
    mutationFn: (zid: string) => documentsApi.restoreZone(docId, zid),
    onSuccess: (d) => {
      onData(d);
      setFeedback({ kind: "ok", text: t("zones.restored") });
    },
    onError: onErr,
  });
  const bulkDelMut = useMutation({
    mutationFn: (ids: string[]) => documentsApi.bulkDeleteZones(docId, ids),
    onSuccess: (d) => {
      onData(d);
      setSelected(new Set());
    },
    onError: onErr,
  });
  const validateMut = useMutation({
    mutationFn: (v: boolean) => documentsApi.validateZones(docId, v),
    onSuccess: onData,
    onError: onErr,
  });
  const addMut = useMutation({
    mutationFn: (v: {
      target: string;
      label: string;
      slide_index: number;
      slide_title: string;
      location: string;
    }) => documentsApi.addZone(docId, v),
    onSuccess: (d) => {
      onData(d);
      setAddTarget("");
      setAddLabel("");
    },
    onError: onErr,
  });

  const data = zonesQuery.data;
  const zones = useMemo(
    () =>
      (data?.zones ?? [])
        .slice()
        .sort(
          (a, b) =>
            a.slide_index - b.slide_index ||
            a.location.localeCompare(b.location) ||
            a.id.localeCompare(b.id),
        ),
    [data],
  );
  const removed = data?.removed ?? [];
  const validated = data?.validated ?? false;
  const dropped = data?.dropped_count ?? 0;

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
  const availableShapes = useMemo(() => {
    const used = new Set(zones.map((z) => z.target).filter(Boolean));
    const out: PptxShape[] = [];
    for (const sl of structure?.slides ?? [])
      for (const sh of sl.shapes ?? []) if (!used.has(sh.id)) out.push(sh);
    return out;
  }, [zones, structure]);
  const kindsPresent = useMemo(
    () => Array.from(new Set(zones.map((z) => z.kind))),
    [zones],
  );

  const classify = (sh: PptxShape): string => {
    const z = zoneByTarget[sh.id];
    if (z) return z.kind === "xxx" || z.kind === "placeholder" ? "zone-regex" : "zone-llm";
    return (sh.text ?? "").trim() ? "label" : "empty";
  };
  const getEdit = (z: ZoneDto) => ({
    label: edits[z.id]?.label ?? z.label ?? "",
    instruction: edits[z.id]?.instruction ?? z.instruction ?? "",
  });
  const setEdit = (z: ZoneDto, field: "label" | "instruction", value: string) =>
    setEdits((p) => ({ ...p, [z.id]: { ...getEdit(z), [field]: value } }));
  const toggleSelect = (zid: string) =>
    setSelected((p) => {
      const n = new Set(p);
      if (n.has(zid)) n.delete(zid);
      else n.add(zid);
      return n;
    });

  const doAdd = () => {
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
    addMut.mutate({
      target: addTarget,
      label: addLabel.trim(),
      slide_index: sh.slide_index,
      slide_title: sh.slide_title,
      location: sh.location,
    });
  };

  const filteredZones = kindFilter
    ? zones.filter((z) => z.kind === kindFilter)
    : zones;
  const busy =
    deleteMut.isPending ||
    bulkDelMut.isPending ||
    validateMut.isPending ||
    addMut.isPending;

  if (zonesQuery.isLoading || structureQuery.isLoading) {
    return (
      <div className="card">
        <div className="empty-state">
          <span className="spinner" /> {t("zones.loading")}
        </div>
      </div>
    );
  }
  if (zonesQuery.error) {
    return (
      <div className="card">
        <div className="error">{zonesQuery.error.message}</div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="card-title">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {t("zones.title")} : {filename}
          {validated ? (
            <span className="badge ok">{t("zones.validated")}</span>
          ) : (
            <span className="badge warn">{t("zones.toValidate")}</span>
          )}
          {dropped > 0 ? (
            <span className="badge danger" title={t("zones.droppedHint")}>
              {t("zones.dropped", { n: dropped })}
            </span>
          ) : null}
        </span>
      </h2>

      <div className="row" style={{ marginBottom: 10 }}>
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          onClick={() => validateMut.mutate(!validated)}
        >
          {validated ? t("zones.unvalidate") : t("zones.validate")}
        </button>
        <button type="button" className="btn ghost" onClick={onClose}>
          {t("zones.close")}
        </button>
        {feedback ? (
          <span className={`grow ${feedback.kind === "ok" ? "" : ""}`}>
            <span className={feedback.kind === "ok" ? "success" : "error"}>
              {feedback.text}
            </span>
          </span>
        ) : null}
      </div>

      {/* Apercu structure : SVG positionne pour PPTX, note + liste pour Word/PDF. */}
      <h3 style={{ fontFamily: "var(--font-display)", fontSize: "0.95rem" }}>
        {t("zones.previewTitle")}
      </h3>
      <small style={{ display: "block", color: "var(--fg-dim)", fontSize: "0.78rem", marginBottom: 6 }}>
        {hasGeometry ? t("zones.previewLegend") : t("zones.previewFlow")}
      </small>
      {!hasGeometry ? (
        <DocFlowPreview
          flow={flowQuery.data}
          loading={flowQuery.isPending}
          error={flowQuery.error?.message ?? null}
          zoneByTarget={zoneByTarget}
          emptyHint={t("zones.flowEmpty")}
          loadingHint={t("zones.flowLoading")}
          onPick={(zid, e) => {
            setPopDelArmed(false);
            setPopover({ x: e.clientX, y: e.clientY, zid });
          }}
        />
      ) : (
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
                    const cls =
                      classify(sh) + (z?.active === false ? " skipped" : "");
                    const b = sh.bbox!;
                    const tip =
                      (z ? `[ ${z.label} ] ` : "") +
                      `${sh.location} - ${sh.kind}` +
                      (sh.text ? ` | "${sh.text.slice(0, 200)}"` : "");
                    return (
                      <g
                        className={`shape ${cls}`}
                        key={sh.id}
                        onClick={(e) => {
                          if (z) {
                            setPopDelArmed(false);
                            setPopover({ x: e.clientX, y: e.clientY, zid: z.id });
                          }
                        }}
                      >
                        <title>{tip}</title>
                        <rect x={b.left} y={b.top} width={b.width} height={b.height} />
                      </g>
                    );
                  })}
                </svg>
                <div className="shape-overlays">
                  {shapes.map((sh) => {
                    const z = zoneByTarget[sh.id];
                    const cls =
                      classify(sh) + (z?.active === false ? " skipped" : "");
                    const b = sh.bbox!;
                    const text =
                      (sh.text ?? "").replace(/\s+/g, " ").trim() ||
                      (z ? z.label : "");
                    if (!text) return null;
                    return (
                      <div
                        className={`shape-overlay ${cls}`}
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
      )}

      {/* Liste */}
      <h3 style={{ marginTop: 18, fontFamily: "var(--font-display)", fontSize: "0.95rem" }}>
        {t("zones.listTitle")}
      </h3>
      <div className="row" style={{ marginBottom: 8, gap: 8 }}>
        <span className="label" style={{ margin: 0 }}>
          {t("zones.filterLabel")}
        </span>
        <select
          className="input"
          style={{ maxWidth: 220 }}
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
        >
          <option value="">{t("zones.filterAll")}</option>
          {kindsPresent.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        {kindFilter ? (
          <span className="file-meta" style={{ fontSize: "0.8rem" }}>
            {filteredZones.length} / {zones.length}
          </span>
        ) : null}
      </div>

      <div className={`bulk-toolbar${selected.size > 0 ? " visible" : ""}`}>
        <span style={{ fontSize: "0.85rem" }}>
          {t("zones.bulk.count", { n: selected.size })}
        </span>
        <button
          type="button"
          className="btn danger small"
          disabled={busy}
          onClick={() => {
            if (!bulkArmed) {
              setBulkArmed(true);
              setTimeout(() => setBulkArmed(false), 3000);
              return;
            }
            setBulkArmed(false);
            bulkDelMut.mutate([...selected]);
          }}
        >
          {bulkArmed ? t("data.confirmAgain") : t("zones.bulk.delete")}
        </button>
        <button
          type="button"
          className="btn ghost small"
          onClick={() => setSelected(new Set())}
        >
          {t("zones.bulk.clear")}
        </button>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th style={{ width: 36, textAlign: "center" }}>
              <input
                type="checkbox"
                title={t("zones.bulk.selectAll")}
                checked={
                  filteredZones.length > 0 &&
                  filteredZones.every((z) => selected.has(z.id))
                }
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? new Set(filteredZones.map((z) => z.id))
                      : new Set(),
                  )
                }
              />
            </th>
            <th>{t("zones.col.location")}</th>
            <th>{t("zones.col.kind")}</th>
            <th>{t("zones.col.label")}</th>
            <th>{t("zones.col.instruction")}</th>
            <th>{t("zones.col.target")}</th>
            <th style={{ textAlign: "right" }}>{t("zones.col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {filteredZones.length === 0 ? (
            <tr>
              <td colSpan={7}>
                <div className="empty-state">{t("zones.empty")}</div>
              </td>
            </tr>
          ) : (
            filteredZones.map((z) => {
              const sh = shapeById[z.target];
              const current = sh
                ? (sh.text ?? "").replace(/\s+/g, " ").slice(0, 80)
                : "";
              const e = getEdit(z);
              return (
                <tr
                  key={z.id}
                  ref={(el) => {
                    if (el) rowRefs.current.set(z.id, el);
                    else rowRefs.current.delete(z.id);
                  }}
                  style={z.active === false ? { opacity: 0.55 } : undefined}
                >
                  <td style={{ textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={selected.has(z.id)}
                      onChange={() => toggleSelect(z.id)}
                    />
                  </td>
                  <td className="file-meta">{z.location || `Slide ${z.slide_index}`}</td>
                  <td className="file-meta">
                    <span className="badge">{z.kind}</span>
                    {z.active === false ? (
                      <span className="badge danger"> {t("zones.inactive")}</span>
                    ) : null}
                  </td>
                  <td>
                    <input
                      className="input"
                      value={e.label}
                      onChange={(ev) => setEdit(z, "label", ev.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      value={e.instruction}
                      placeholder={t("zones.col.instructionPlaceholder")}
                      onChange={(ev) => setEdit(z, "instruction", ev.target.value)}
                    />
                  </td>
                  <td className="file-meta" title={z.target}>
                    <code style={{ fontSize: "0.78rem" }}>{z.target || "-"}</code>
                    {current ? (
                      <>
                        <br />
                        <small style={{ color: "var(--fg-dim)" }}>{current}</small>
                      </>
                    ) : null}
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button
                      type="button"
                      className="btn secondary small"
                      style={{ marginRight: 4 }}
                      disabled={saveMut.isPending}
                      onClick={() =>
                        saveMut.mutate({ zid: z.id, label: e.label, instruction: e.instruction })
                      }
                    >
                      {t("zones.save")}
                    </button>
                    <button
                      type="button"
                      className={`btn small ${delArmed === z.id ? "danger" : "ghost"}`}
                      disabled={busy}
                      onClick={() => {
                        if (delArmed !== z.id) {
                          setDelArmed(z.id);
                          setTimeout(
                            () => setDelArmed((c) => (c === z.id ? null : c)),
                            3000,
                          );
                          return;
                        }
                        setDelArmed(null);
                        deleteMut.mutate(z.id);
                      }}
                    >
                      {delArmed === z.id ? t("data.confirmAgain") : t("zones.delete")}
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      {/* Corbeille */}
      {removed.length > 0 ? (
        <>
          <h3 style={{ marginTop: 18, fontFamily: "var(--font-display)", fontSize: "0.95rem" }}>
            {t("zones.removedTitle")}
          </h3>
          <small style={{ display: "block", color: "var(--fg-dim)", fontSize: "0.78rem", marginBottom: 6 }}>
            {t("zones.removedLegend")}
          </small>
          <table className="data-table">
            <tbody>
              {removed.map((z) => (
                <tr key={z.id}>
                  <td className="file-meta">{z.location || `Slide ${z.slide_index}`}</td>
                  <td className="file-meta">
                    <span className="badge">{z.kind}</span>
                  </td>
                  <td>{z.label || "-"}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button
                      type="button"
                      className="btn secondary small"
                      disabled={restoreMut.isPending}
                      onClick={() => restoreMut.mutate(z.id)}
                    >
                      {t("zones.restore")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      {/* Ajouter */}
      <h3 style={{ marginTop: 18, fontFamily: "var(--font-display)", fontSize: "0.95rem" }}>
        {t("zones.addTitle")}
      </h3>
      {availableShapes.length === 0 ? (
        <small style={{ color: "var(--fg-dim)" }}>{t("zones.noShapesAvailable")}</small>
      ) : (
        <div className="form">
          <label>
            <div className="label">{t("zones.col.target")}</div>
            <select
              className="input"
              value={addTarget}
              onChange={(ev) => setAddTarget(ev.target.value)}
            >
              <option value="">--</option>
              {availableShapes.map((s) => {
                const prev = (s.text ?? "").replace(/\s+/g, " ").slice(0, 60);
                return (
                  <option key={s.id} value={s.id}>
                    {s.location} - {s.kind}
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
              onChange={(ev) => setAddLabel(ev.target.value)}
            />
          </label>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              disabled={addMut.isPending}
              onClick={doAdd}
            >
              {t("zones.addAction")}
            </button>
          </div>
        </div>
      )}

      {popover
        ? (() => {
            const z = zones.find((zz) => zz.id === popover.zid);
            if (!z) return null;
            return (
              <ZonePopover
                x={popover.x}
                y={popover.y}
                meta={`${z.location || `Slide ${z.slide_index}`} - ${z.kind}`}
                label={z.label || "-"}
                onClose={() => setPopover(null)}
              >
                <button
                  type="button"
                  className="btn secondary small"
                  onClick={() => {
                    const row = rowRefs.current.get(z.id);
                    if (row) {
                      row.scrollIntoView({ behavior: "smooth", block: "center" });
                      const inp = row.querySelector("input.input") as HTMLInputElement | null;
                      inp?.focus();
                    }
                    setPopover(null);
                  }}
                >
                  {t("zones.edit")}
                </button>
                <button
                  type="button"
                  className={`btn small ${popDelArmed ? "danger" : "ghost"}`}
                  onClick={() => {
                    if (!popDelArmed) {
                      setPopDelArmed(true);
                      return;
                    }
                    deleteMut.mutate(z.id);
                    setPopover(null);
                  }}
                >
                  {popDelArmed ? t("data.confirmAgain") : t("zones.delete")}
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
