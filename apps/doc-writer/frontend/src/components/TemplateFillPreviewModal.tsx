import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  documentsApi,
  sessionsApi,
  type FlowDto,
  type PreviewPptxDto,
  type ZoneDto,
} from "../lib/api";
import { DocFlowPreview } from "./DocFlowPreview";
import { ZonePopover } from "./ZonePopover";

type Props = {
  sessionId: string;
  templateDocId: string;
  defaultFilename?: string;
  onClose: () => void;
};

type Status = "filled" | "empty" | "skipped";

// Apercu de rendu Word/PDF : pendant flow-based de PptxPreviewModal. Montre le
// contenu REELLEMENT rempli zone par zone (mapping = ce qui sera ecrit), permet
// l'edition/consigne/skip/refill, puis telecharge CE mapping via render (pas de
// nouvelle passe LLM) -> "ce que tu vois = ce que tu telecharges". Pas de SVG
// (Word/PDF n'ont pas de geometrie) : on reutilise DocFlowPreview + le flux.
export function TemplateFillPreviewModal({
  sessionId,
  templateDocId,
  defaultFilename,
  onClose,
}: Props) {
  const { t } = useTranslation();

  const previewQuery = useQuery<PreviewPptxDto, ApiClientError>({
    queryKey: ["fill-preview", sessionId],
    queryFn: () => sessionsApi.previewPptx(sessionId),
  });
  const flowQuery = useQuery<FlowDto, ApiClientError>({
    queryKey: ["documents", templateDocId, "flow"],
    queryFn: () => documentsApi.flow(templateDocId),
  });

  const [zones, setZones] = useState<ZoneDto[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filename, setFilename] = useState(defaultFilename ?? "");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [popover, setPopover] = useState<{ x: number; y: number; zid: string } | null>(
    null,
  );
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map());
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
    // Prose Word inactive par defaut -> pre-ignoree (active === false).
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

  const zoneByTarget = useMemo(() => {
    const m: Record<string, ZoneDto> = {};
    for (const z of zones) if (z.target) m[z.target] = z;
    return m;
  }, [zones]);

  const scrollToRow = (zid: string) => {
    const row = rowRefs.current.get(zid);
    if (!row) return;
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    const field = row.querySelector("textarea, input") as HTMLElement | null;
    setTimeout(() => field?.focus(), 250);
  };

  const statusOf = (zid: string): Status => {
    if (skipped.has(zid)) return "skipped";
    return (mapping[zid] ?? "").trim() ? "filled" : "empty";
  };
  const setMap = (zid: string, v: string) => setMapping((p) => ({ ...p, [zid]: v }));
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

  const toggleSelect = (zid: string) =>
    setSelected((p) => {
      const n = new Set(p);
      if (n.has(zid)) n.delete(zid);
      else n.add(zid);
      return n;
    });

  const download = async () => {
    setBusy(true);
    setFeedback({ kind: "ok", text: t("pptx.preview.rendering") });
    const finalMapping: Record<string, string> = {};
    for (const z of zones) {
      if (skipped.has(z.id)) {
        // Marqueur regex ignore -> vide le marqueur ; cadre ignore -> omis
        // (le template conserve son contenu d'origine).
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
        return a.location.localeCompare(b.location) || a.id.localeCompare(b.id);
      }),
    [zones],
  );

  const loading = previewQuery.isLoading || flowQuery.isLoading;
  const loadError = previewQuery.error || flowQuery.error;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-header">
          <h2>{t("template.fill.title")}</h2>
          <span className="badge ok">
            {t("pptx.preview.zonesCount", { n: zones.length })}
          </span>
          <button type="button" className="btn ghost small" onClick={onClose}>
            {t("zones.close")}
          </button>
        </div>

        {loading ? (
          <div
            className="modal-body"
            style={{ display: "block", textAlign: "center", padding: 40 }}
          >
            <span className="spinner" /> {t("template.fill.loading")}
          </div>
        ) : loadError ? (
          <div className="modal-body" style={{ display: "block" }}>
            <div className="error">{loadError.message}</div>
          </div>
        ) : (
          <div className="modal-body">
            {/* Gauche : apercu du rendu (flux document + contenu rempli) */}
            <div>
              <small
                style={{
                  display: "block",
                  color: "var(--fg-dim)",
                  fontSize: "0.78rem",
                  marginBottom: 6,
                }}
              >
                {t("template.fill.legend")}
              </small>
              <DocFlowPreview
                flow={flowQuery.data}
                loading={false}
                error={null}
                zoneByTarget={zoneByTarget}
                mapping={mapping}
                skippedIds={skipped}
                emptyHint={t("zones.flowEmpty")}
                loadingHint={t("zones.flowLoading")}
                onPick={(zid, e) => {
                  setPopover({ x: e.clientX, y: e.clientY, zid });
                }}
              />
            </div>

            {/* Droite : edition zone par zone */}
            <div>
              <h3
                style={{
                  marginTop: 0,
                  fontFamily: "'Orbitron',sans-serif",
                  fontSize: "0.9rem",
                }}
              >
                {t("pptx.preview.editTitle")}
              </h3>
              <small
                style={{
                  display: "block",
                  color: "var(--fg-dim)",
                  fontSize: "0.78rem",
                  marginBottom: 8,
                }}
              >
                {t("pptx.preview.editHint")}
              </small>

              {sortedZones.length === 0 ? (
                <div className="empty-state">{t("pptx.preview.noZones")}</div>
              ) : (
                <>
                  <label
                    className="checkbox"
                    style={{ fontSize: "0.78rem", marginBottom: 6 }}
                  >
                    <input
                      type="checkbox"
                      checked={
                        sortedZones.length > 0 && selected.size === sortedZones.length
                      }
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
                    <button
                      type="button"
                      className="btn secondary small"
                      disabled={busy}
                      onClick={() => refill([...selected], false)}
                    >
                      {t("pptx.preview.refill")}
                    </button>
                    <button
                      type="button"
                      className="btn secondary small"
                      disabled={busy}
                      onClick={() => refill([...selected], true)}
                    >
                      {t("pptx.preview.force")}
                    </button>
                    <button
                      type="button"
                      className="btn ghost small"
                      disabled={busy}
                      onClick={() => bulkSetActive([...selected], false)}
                    >
                      {t("pptx.preview.skipSel")}
                    </button>
                    <button
                      type="button"
                      className="btn ghost small"
                      disabled={busy}
                      onClick={() => bulkSetActive([...selected], true)}
                    >
                      {t("pptx.preview.unskipSel")}
                    </button>
                    <button
                      type="button"
                      className="btn ghost small"
                      disabled={busy}
                      onClick={clearSelected}
                    >
                      {t("pptx.preview.clear")}
                    </button>
                  </div>
                  <small
                    style={{
                      display: "block",
                      color: "var(--fg-dim)",
                      fontSize: "0.78rem",
                      margin: "4px 0 8px",
                    }}
                  >
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
                                  {z.location || "-"} - {z.kind}
                                </span>
                                <span className={`zone-status ${st}`}>
                                  {t(`pptx.preview.status.${st}`)}
                                </span>
                                <button
                                  type="button"
                                  className="btn secondary small"
                                  style={{
                                    marginLeft: "auto",
                                    padding: "2px 8px",
                                    fontSize: "0.7rem",
                                  }}
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
            className="btn primary"
            disabled={busy || loading}
            onClick={download}
          >
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
                meta={`${z.location || "-"} - ${z.kind} · ${t(
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
