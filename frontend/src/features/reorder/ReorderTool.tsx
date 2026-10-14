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

import { processPDF } from "../../shared/api";
import { Button } from "../../shared/components/Button";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { renderPdfThumbnails, type PageThumbnail } from "./pdfPreview";

export function ReorderTool() {
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
    )
      .then((pages) => {
        if (!controller.signal.aborted) {
          setThumbnails(pages);
          setOrder(pages.map((page) => page.pageNumber));
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setPreviewError(
            reason instanceof Error
              ? reason.message
              : "Impossible de créer les miniatures de ce PDF.",
          );
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
      setError("Sélectionnez un PDF et attendez la création des miniatures.");
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("order", JSON.stringify(order));
    try {
      await processPDF("reorder", data, "reordered.pdf");
      setSuccess(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "La réorganisation a échoué.");
    } finally {
      setWorking(false);
    }
  };

  const thumbnailByPage = new Map(thumbnails.map((thumbnail) => [thumbnail.pageNumber, thumbnail]));

  return (
    <form className="reorder-workflow" onSubmit={submit}>
      <section className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>Charger le PDF</h2>
            <p>Les miniatures sont générées dans votre navigateur.</p>
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
          label="Déposez votre PDF ici"
          description="Le fichier n'est envoyé au serveur qu'après validation de l'ordre"
        />
        {file ? (
          <div className="selected-file">
            <span className="file-row-icon">
              <FileText size={17} aria-hidden="true" />
            </span>
            <span className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size)}</span>
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
              aria-label="Retirer le fichier"
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
      </section>

      <section className="panel thumbnail-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>Organiser les pages</h2>
            <p>Faites glisser les pages ou utilisez le clavier pour les déplacer.</p>
          </div>
        </div>

        {previewLoading ? (
          <p className="preview-status" role="status">
            <span className="spinner" aria-hidden="true" />
            Création des miniatures : {progress.completed}
            {progress.total > 0 ? ` / ${progress.total}` : ""}
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
              <div className="thumbnail-grid" aria-label="Pages du document, dans l'ordre de sortie">
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
            <span>Les miniatures des pages apparaîtront ici.</span>
          </div>
        )}

        <div className="reorder-submit">
          <div className="output-preview">
            <span className="output-icon">
              <FileText size={21} aria-hidden="true" />
            </span>
            <span>
              <strong>reordered.pdf</strong>
              <small>Document réorganisé</small>
            </span>
          </div>
          <Button
            type="submit"
            disabled={working || previewLoading || order.length === 0}
            className="action-button"
          >
            {working ? <span className="spinner" aria-hidden="true" /> : <Grip size={18} />}
            {working ? "Réorganisation…" : "Réorganiser"}
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
              Le fichier reordered.pdf a été téléchargé.
            </p>
          ) : null}
        </div>
      </section>
    </form>
  );
}

type SortablePageProps = {
  thumbnail: PageThumbnail;
  position: number;
};

function SortablePage({ thumbnail, position }: SortablePageProps) {
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
    >
      <img
        className="page-thumbnail"
        src={thumbnail.dataUrl}
        alt={`Miniature de la page ${thumbnail.pageNumber}`}
        draggable={false}
      />
      <div className="page-card-caption">
        <span>Position {position}</span>
        <span>Page {thumbnail.pageNumber}</span>
      </div>
    </article>
  );
}
