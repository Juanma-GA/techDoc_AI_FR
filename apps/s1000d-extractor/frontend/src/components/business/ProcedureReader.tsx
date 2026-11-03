import { Button } from "@internal/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import { pdfCutApi } from "../../lib/api";
import { formatApiError } from "../../lib/migrationUtils";
import { preliminaryApi } from "../../lib/preliminaryApi";
import type { ProcedureReview, ReaderPosition, ReviewPassage, SourcePage } from "../../lib/preliminaryTypes";

type Props = {
  docId: string;
  dmId: string;
  review: ProcedureReview;
  sourceFormat: string;
  selectedId: string | null;
  jump: number;
  onPosition: (position: ReaderPosition) => void;
};

function SourceExcerpt({ item, selected }: { item: ReviewPassage; selected: boolean }) {
  const content = selected ? <mark className="bg-warning text-bg">{item.source_text}</mark> : item.source_text;
  return (
    <div data-passage={item.id} tabIndex={selected ? -1 : undefined} className="py-2 whitespace-pre-wrap">
      {item.kind === "section" || item.kind === "title" ? <h4 className="font-semibold">{content}</h4>
        : item.row !== null ? (
          <table className="w-full border"><tbody><tr>
            {item.source_text.split(" | ").map((cell, index) => (
              <td key={index} className={`border p-2 ${selected ? "bg-warning text-bg" : ""}`}>{cell}</td>
            ))}
          </tr></tbody></table>
        ) : item.kind === "item" ? <ul className="list-disc pl-4"><li>{content}</li></ul>
          : item.kind === "admonition" ? <blockquote className="border-l-4 border-warning pl-3">{content}</blockquote>
            : <p>{content}</p>}
    </div>
  );
}

function PdfSourcePage({ docId, dmId, page, passages, selectedId, container, jump }: {
  docId: string; dmId: string; page: SourcePage; passages: ReviewPassage[];
  selectedId: string | null; container: RefObject<HTMLDivElement>;
  jump: number;
}) {
  const { t } = useTranslation();
  const element = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) {
        setVisible(true);
        observer.disconnect();
      }
    }, { root: container.current, rootMargin: `${window.innerHeight}px` });
    if (element.current) observer.observe(element.current);
    return () => observer.disconnect();
  }, [container]);
  const anchors = useQuery({
    queryKey: ["preliminary-anchors", docId, dmId, page.page, passages.map((p) => p.id).join(",")],
    queryFn: () => preliminaryApi.anchors(docId, dmId, page.page),
    enabled: visible,
    staleTime: Infinity,
  });
  const boxes = selectedId ? anchors.data?.anchors[selectedId] ?? [] : [];
  useEffect(() => {
    if (!jump || !selectedId || imageError || !anchors.data?.anchors[selectedId]?.length) return;
    element.current?.querySelector("[data-source-anchor]")?.scrollIntoView({
      behavior: "smooth", block: "center",
    });
  }, [jump, selectedId, imageError, anchors.data]);
  return (
    <div ref={element}>
      <div className="relative w-full bg-bg-2" style={{ aspectRatio: page.width / page.height }}>
        {visible && !imageError ? (
          <img className="absolute inset-0 w-full h-full" alt={t("preliminary.pdfPage", { page: page.page })}
            src={`${pdfCutApi.previewUrl(docId, page.page)}?attempt=${attempt}`} loading="lazy"
            onError={() => setImageError(true)} />
        ) : null}
        {!imageError ? boxes.map(([x0, y0, x1, y1], index) => (
          <div key={index} data-source-anchor data-source-passage={selectedId} aria-hidden="true" className="absolute pointer-events-none border border-warning bg-warning opacity-20"
            style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`,
              width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }} />
        )) : null}
      </div>
      {imageError ? (
        <div role="alert" className="p-3 text-danger">
          {t("preliminary.imageError")}
          <Button variant="secondary" size="sm" onClick={() => { setImageError(false); setAttempt((n) => n + 1); }}>
            {t("preliminary.retry")}
          </Button>
        </div>
      ) : null}
      {anchors.error ? (
        <div role="alert" className="text-danger">
          {t("preliminary.anchorError")}: {formatApiError(t, anchors.error)}
          <Button variant="secondary" size="sm" onClick={() => void anchors.refetch()}>{t("preliminary.retry")}</Button>
        </div>
      ) : null}
      {selectedId && passages.some((p) => p.id === selectedId) && anchors.data && !boxes.length ? (
        <p role="status" className="text-warning">{t("preliminary.missingPdfAnchor")}</p>
      ) : null}
    </div>
  );
}

export function ProcedureReader({ docId, dmId, review, sourceFormat, selectedId, jump, onPosition }: Props) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const restored = useRef(false);
  const initialPosition = useRef(review.position);
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;
  const pdf = sourceFormat === "pdf";
  const manifest = useQuery({
    queryKey: ["preliminary-pages", docId, dmId, review.fingerprint],
    queryFn: () => preliminaryApi.pages(docId, dmId),
    enabled: pdf,
    staleTime: Infinity,
  });
  const grouped = new Map<number, ReviewPassage[]>();
  for (const passage of review.passages) {
    const page = passage.page ?? 0;
    grouped.set(page, [...(grouped.get(page) ?? []), passage]);
  }
  const pageNumbers = (pdf ? (manifest.data ?? []).map((page) => page.page) : [...grouped.keys()])
    .sort((a, b) => a - b);
  const ready = !pdf || manifest.isSuccess;
  const selectedPassage = review.passages.find((passage) => passage.id === selectedId);
  const sourcePageUnavailable = pdf && ready && selectedPassage
    && !manifest.data?.some((page) => page.page === selectedPassage.page);

  useEffect(() => {
    if (!ready || restored.current || !container.current) return;
    const frame = requestAnimationFrame(() => {
      if (container.current) container.current.scrollTop = initialPosition.current.scroll_top;
      restored.current = true;
    });
    return () => cancelAnimationFrame(frame);
  }, [ready]);

  useEffect(() => {
    if (!jump || !selectedId || !ready || !container.current) return;
    const element = container.current;
    const selectedPage = review.passages.find((passage) => passage.id === selectedId)?.page;
    const page = Array.from(element.querySelectorAll<HTMLElement>("[data-page]"))
      .find((entry) => Number(entry.dataset.page) === selectedPage);
    const target = pdf
      ? Array.from(element.querySelectorAll<HTMLElement>("[data-source-passage]"))
        .find((entry) => entry.dataset.sourcePassage === selectedId) ?? page
      : Array.from(element.querySelectorAll<HTMLElement>("[data-passage]"))
        .find((entry) => entry.dataset.passage === selectedId);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    (pdf ? page ?? element : target)?.focus({ preventScroll: true });
    onPosition({
      page: selectedPage ?? initialPosition.current.page,
      scroll_top: element.scrollTop, selected_id: selectedId,
    });
  // Autosave responses must not reposition reading.
  }, [jump, selectedId, ready]);

  const capture = () => {
    const element = container.current;
    if (!element || !restored.current) return;
    const top = element.getBoundingClientRect().top;
    const pages = Array.from(element.querySelectorAll<HTMLElement>("[data-page]"));
    const current = pages.find((page) => page.getBoundingClientRect().bottom > top + 1);
    onPosition({
      page: Number(current?.dataset.page) || initialPosition.current.page,
      scroll_top: element.scrollTop, selected_id: selectedRef.current,
    });
  };
  return (
    <section className="min-w-0 space-y-2" aria-label={t("preliminary.reader")}>
      {!pdf ? <p className="text-sm text-fg-dim">{t("preliminary.wordHelp")}</p> : null}
      {manifest.error ? (
        <div role="alert" className="text-danger">
          {t("preliminary.readerError")}: {formatApiError(t, manifest.error)}
          <Button variant="secondary" onClick={() => void manifest.refetch()}>{t("preliminary.retry")}</Button>
        </div>
      ) : null}
      {!ready && !manifest.error ? <p role="status">{t("preliminary.loading")}</p> : null}
      {sourcePageUnavailable ? <p role="status" className="text-warning">{t("preliminary.sourcePageUnavailable")}</p> : null}
      <div ref={container} data-testid="procedure-reader" tabIndex={0} role="region"
        aria-label={t("preliminary.reader")} onScroll={capture}
        className="h-96 overflow-y-auto overscroll-contain rounded-sm border bg-bg-2 px-3 pb-3 pt-0 space-y-4 lg:h-[70vh]">
        {ready ? pageNumbers.map((pageNumber) => {
          const items = grouped.get(pageNumber) ?? [];
          const page = manifest.data?.find((p) => p.page === pageNumber);
          return (
            <section key={pageNumber} data-page={pageNumber || initialPosition.current.page}
              tabIndex={pdf ? -1 : undefined} aria-label={t(pdf ? "preliminary.page" : "preliminary.readingPage", { page: pageNumber })}
              className="bg-card">
              <h3 className="sticky top-0 z-10 bg-card border-b p-2 font-mono">
                {pageNumber ? t(pdf ? "preliminary.page" : "preliminary.readingPage", { page: pageNumber })
                  : t("preliminary.unlocated")}
              </h3>
              {pdf && page ? <PdfSourcePage docId={docId} dmId={dmId} page={page}
                passages={items} selectedId={selectedId} container={container} jump={jump} /> : null}
              {!pdf ? <div className="p-3">
                {items.map((item) => <SourceExcerpt key={item.id} item={item} selected={item.id === selectedId} />)}
              </div> : null}
            </section>
          );
        }) : null}
        {ready && !pageNumbers.length ? <p>{t(pdf ? "preliminary.noPdfPages" : "preliminary.noPassages")}</p> : null}
      </div>
    </section>
  );
}
