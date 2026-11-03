import { useRef, useState, type PointerEvent, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import { commentBoxFromDrag, type CommentBox, type CommentPoint } from "./commentBox";

type CommentMarker = {
  id: number;
  box: CommentBox;
};

type CommentPagePreviewProps = {
  canvasRef: RefObject<HTMLCanvasElement>;
  pageNumber: number;
  pageSize: { width: number; height: number };
  ready: boolean;
  disabled: boolean;
  comments: CommentMarker[];
  draftBox: CommentBox | null;
  onBoxSelected: (box: CommentBox) => void;
};

type DragStart = CommentPoint & { pointerId: number };

export function CommentPagePreview({
  canvasRef,
  pageNumber,
  pageSize,
  ready,
  disabled,
  comments,
  draftBox,
  onBoxSelected,
}: CommentPagePreviewProps) {
  const { t } = useTranslation();
  const pageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragStart | null>(null);
  const [dragBox, setDragBox] = useState<CommentBox | null>(null);

  const pointerPosition = (event: PointerEvent<HTMLDivElement>): CommentPoint | null => {
    const bounds = pageRef.current?.getBoundingClientRect();
    if (!bounds || bounds.width === 0 || bounds.height === 0) return null;
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  };

  const nextBox = (event: PointerEvent<HTMLDivElement>) => {
    const start = dragRef.current;
    const position = pointerPosition(event);
    if (!start || !position || start.pointerId !== event.pointerId) return null;
    return commentBoxFromDrag(start, position);
  };

  const updateDrag = (event: PointerEvent<HTMLDivElement>) => {
    const box = nextBox(event);
    if (box) setDragBox(box);
  };
  const activeBox = dragBox ?? draftBox;

  return (
    <div
      ref={pageRef}
      className={`comments-pdf-page${ready ? " is-ready" : ""}${ready && !disabled ? " is-drawable" : ""}`}
      style={{ aspectRatio: `${pageSize.width} / ${pageSize.height}` }}
      onPointerDown={(event) => {
        if (!ready || disabled || event.button !== 0) return;
        const position = pointerPosition(event);
        if (!position) return;
        event.currentTarget.setPointerCapture?.(event.pointerId);
        dragRef.current = { ...position, pointerId: event.pointerId };
        setDragBox(commentBoxFromDrag(position, position));
      }}
      onPointerMove={updateDrag}
      onPointerUp={(event) => {
        const box = nextBox(event);
        if (box) onBoxSelected(box);
        dragRef.current = null;
        setDragBox(null);
      }}
      onPointerCancel={() => {
        dragRef.current = null;
        setDragBox(null);
      }}
    >
      <canvas ref={canvasRef} aria-label={t("comments.pagePreview", { page: pageNumber })} />
      {comments.map((comment, index) => (
        <div
          key={comment.id}
          className="comments-highlight-box"
          style={{
            left: `${comment.box.x * 100}%`,
            top: `${comment.box.y * 100}%`,
            width: `${comment.box.width * 100}%`,
            height: `${comment.box.height * 100}%`,
          }}
          aria-hidden="true"
        >
          <span className="comments-box-number">{index + 1}</span>
        </div>
      ))}
      {activeBox ? (
        <div
          className="comments-highlight-box is-draft"
          style={{
            left: `${activeBox.x * 100}%`,
            top: `${activeBox.y * 100}%`,
            width: `${activeBox.width * 100}%`,
            height: `${activeBox.height * 100}%`,
          }}
          aria-hidden="true"
        />
      ) : null}
    </div>
  );
}
