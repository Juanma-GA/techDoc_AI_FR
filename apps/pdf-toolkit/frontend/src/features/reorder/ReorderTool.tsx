import { useEffect, useState, type FormEvent } from "react";
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  type DragEndEvent,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  rectSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { FileText, Grip, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatOperationError, processPDF } from "../../shared/api";
import { Button, Card, Spinner } from "@internal/ui";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { renderPdfThumbnails, type PageThumbnail } from "./pdfPreview";

export function ReorderTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [file, setFile] = useState<File | null>(null);
  const [thumbnails, setThumbnails] = useState<PageThumbnail[]>([]);
  const [order, setOrder] = useState<number[]>([]);
  const [previewError, setPreviewError] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [progress, setProgress] = useState({ completed: 0, total: 0 });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  useEffect(() => {
    if (!file) {
      setThumbnails([]);
      setOrder([]);
      setPreviewLoading(false);
      setProgress({ completed: 0, total: 0 });
      return;
    }

    const controller = new AbortController();
    setThumbnails([]);
    setOrder([]);
    setPreviewError("");
    setPreviewLoading(true);
    setProgress({ completed: 0, total: 0 });

    void renderPdfThumbnails(
      file,
      (completed, total) => setProgress({ completed, total }),
      controller.signal,
      {
        emptyDocument: t("reorder.emptyDocument"),
        canvasUnavailable: t("reorder.canvasUnavailable"),
      },
    )
      .then((pages) => {
        if (!controller.signal.aborted) {
          setThumbnails(pages);
          setOrder(pages.map((page) => page.pageNumber));
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setPreviewError(reason instanceof Error ? reason.message : t("reorder.previewFailed"));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setPreviewLoading(false);
        }
      });

    return () => controller.abort();
  }, [file]);

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) {
      return;
    }
    setOrder((current) => {
      const source = current.findIndex((page) => String(page) === String(active.id));
      const target = current.findIndex((page) => String(page) === String(over.id));
      return source < 0 || target < 0 ? current : arrayMove(current, source, target);
    });
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || order.length === 0) {
      setError(t("reorder.selectAndWait"));
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("order", JSON.stringify(order));
    try {
      await processPDF("reorder", data, "reordered.pdf", t);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.reorderFailed"));
    } finally {
      setWorking(false);
    }
  };

  const thumbnailByPage = new Map(thumbnails.map((thumbnail) => [thumbnail.pageNumber, thumbnail]));

  return (
    <form className="workflow-grid reorder-workflow" onSubmit={submit}>
      <Card className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("reorder.stepFile")}</h2>
            <p>{t("reorder.stepFileDescription")}</p>
          </div>
        </div>
        <FileDropzone
          disabled={working}
          onFiles={(incoming) => {
            setFile(incoming[0] ?? null);
            setError("");
            setSuccess(false);
          }}
          onError={setError}
          label={t("files.dropLabel")}
          description={t("reorder.dropDescription")}
        />
        {file ? (
          <div className="selected-file">
            <span className="file-row-icon">
              <FileText size={17} aria-hidden="true" />
            </span>
            <span className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size, language)}</span>
            </span>
            <Button
              variant="ghost"
              className="icon-button remove-button"
              disabled={working}
              onClick={() => {
                setFile(null);
                setPreviewError("");
                setError("");
              }}
              aria-label={t("files.remove")}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
      </Card>

      <Card className="panel thumbnail-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("reorder.stepPages")}</h2>
            <p>{t("reorder.stepPagesDescription")}</p>
          </div>
        </div>

        {previewLoading ? (
          <p className="preview-status" role="status">
            <Spinner aria-label={t("common.loading")} />
            {progress.total > 0
              ? t("reorder.previewProgress", progress)
              : t("reorder.previewProgressPending", progress)}
          </p>
        ) : null}
        {previewError ? (
          <p className="feedback feedback-error" role="alert">
            {previewError}
          </p>
        ) : null}
        {order.length > 0 ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={order} strategy={rectSortingStrategy}>
              <div className="thumbnail-grid" aria-label={t("reorder.pagesAriaLabel")}>
                {order.map((pageNumber, index) => {
                  const thumbnail = thumbnailByPage.get(pageNumber);
                  return thumbnail ? (
                    <SortablePage
                      key={pageNumber}
                      thumbnail={thumbnail}
                      position={index + 1}
                    />
                  ) : null;
                })}
              </div>
            </SortableContext>
          </DndContext>
        ) : (
          <div className="thumbnail-empty">
            <Grip size={22} aria-hidden="true" />
            <span>{t("reorder.emptyThumbnails")}</span>
          </div>
        )}

        <div className="reorder-submit">
          <div className="output-preview">
            <span className="output-icon">
              <FileText size={21} aria-hidden="true" />
            </span>
            <span>
              <strong>reordered.pdf</strong>
              <small>{t("reorder.outputDescription")}</small>
            </span>
          </div>
          <Button
            type="submit"
            disabled={working || previewLoading || order.length === 0}
            className="action-button"
          >
            {working ? <Spinner aria-label={t("common.loading")} /> : <Grip size={18} />}
            {working ? t("reorder.working") : t("reorder.action")}
          </Button>
        </div>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("reorder.success", { fileName: "reordered.pdf" })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}

type SortablePageProps = {
  thumbnail: PageThumbnail;
  position: number;
};

function SortablePage({ thumbnail, position }: SortablePageProps) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: thumbnail.pageNumber,
  });

  return (
    <article
      ref={setNodeRef}
      className={`page-card${isDragging ? " page-card-dragging" : ""}`}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      {...attributes}
      {...listeners}
      aria-label={t("reorder.thumbnailAlt", { page: thumbnail.pageNumber })}
    >
      <img
        className="page-thumbnail"
        src={thumbnail.dataUrl}
        alt={t("reorder.thumbnailAlt", { page: thumbnail.pageNumber })}
        draggable={false}
      />
      <div className="page-card-caption">
        <span>{t("reorder.position", { position })}</span>
        <span>{t("reorder.page", { page: thumbnail.pageNumber })}</span>
      </div>
    </article>
  );
}
