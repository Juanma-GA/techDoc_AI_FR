import type { KeyboardEvent, PointerEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@internal/ui";

export type ResizeCorner = "topLeft" | "topRight" | "bottomLeft" | "bottomRight";

type ResizeHandlesProps = {
  boxLabel: string;
  disabled: boolean;
  onResizeStart: (corner: ResizeCorner, event: PointerEvent<HTMLButtonElement>) => void;
  onResizeMove: (event: PointerEvent<HTMLButtonElement>) => void;
  onResizeEnd: (event: PointerEvent<HTMLButtonElement>) => void;
  onResizeKeyDown: (corner: ResizeCorner, event: KeyboardEvent<HTMLButtonElement>) => void;
};

const corners: ResizeCorner[] = ["topLeft", "topRight", "bottomLeft", "bottomRight"];

export function ResizeHandles({
  boxLabel,
  disabled,
  onResizeStart,
  onResizeMove,
  onResizeEnd,
  onResizeKeyDown,
}: ResizeHandlesProps) {
  const { t } = useTranslation();

  return (
    <>
      {corners.map((corner) => (
        <Button
          key={corner}
          type="button"
          variant="ghost"
          className={`signature-resize-handle signature-resize-handle-${corner}`}
          aria-label={t("signature.resizeHandle", {
            box: boxLabel,
            corner: t(`signature.corner.${corner}`),
          })}
          disabled={disabled}
          onPointerDown={(event) => onResizeStart(corner, event)}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
          onKeyDown={(event) => onResizeKeyDown(corner, event)}
        >
          <span aria-hidden="true" />
        </Button>
      ))}
    </>
  );
}
