import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Eraser, PenLine, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@internal/ui";
import { validateImageFile } from "../../shared/files";
import { MAX_SIGNATURE_IMAGE_SIZE } from "./limits";

type SignaturePadProps = {
  disabled: boolean;
  onSave: (file: File) => void;
  onClear: () => void;
};

const canvasWidth = 960;
const canvasHeight = 300;

export function SignaturePad({ disabled, onSave, onClear }: SignaturePadProps) {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activePointer = useRef<number | null>(null);
  const [hasDrawing, setHasDrawing] = useState(false);
  const [error, setError] = useState("");

  const getPoint = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - bounds.left) / bounds.width) * canvas.width,
      y: ((event.clientY - bounds.top) / bounds.height) * canvas.height,
    };
  };

  const startDrawing = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    event.preventDefault();
    const canvas = event.currentTarget;
    const context = canvas.getContext("2d");
    if (!context) {
      setError(t("signature.canvasUnavailable"));
      return;
    }
    activePointer.current = event.pointerId;
    if (typeof canvas.setPointerCapture === "function") {
      canvas.setPointerCapture(event.pointerId);
    }
    const point = getPoint(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = 6;
    context.strokeStyle = "rgba(0, 0, 0, 1)";
    setHasDrawing(true);
    setError("");
  };

  const draw = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (activePointer.current !== event.pointerId) return;
    const context = event.currentTarget.getContext("2d");
    if (!context) {
      setError(t("signature.canvasUnavailable"));
      return;
    }
    const point = getPoint(event);
    context.lineTo(point.x, point.y);
    context.stroke();
  };

  const stopDrawing = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (activePointer.current !== event.pointerId) return;
    activePointer.current = null;
    if (typeof event.currentTarget.releasePointerCapture === "function") {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const clearDrawing = () => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawing(false);
    setError("");
    onClear();
  };

  const saveDrawing = () => {
    const canvas = canvasRef.current;
    if (!canvas || !hasDrawing) return;
    canvas.toBlob((blob) => {
      if (!blob) {
        setError(t("signature.canvasExportFailed"));
        return;
      }
      onSave(new File([blob], "signature.png", { type: "image/png" }));
      setError("");
    }, "image/png");
  };

  const importImage = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;

    const validationError = validateImageFile(
      file,
      {
        tooLarge: (name) => t("signature.imageTooLarge", { name }),
        notImage: (name) => t("files.notImage", { name }),
      },
      MAX_SIGNATURE_IMAGE_SIZE,
    );
    if (validationError) {
      setError(validationError);
      return;
    }
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawing(false);
    setError("");
    onSave(file);
  };

  return (
    <div className="signature-pad-section">
      <canvas
        ref={canvasRef}
        className="signature-pad"
        width={canvasWidth}
        height={canvasHeight}
        aria-label={t("signature.canvasLabel")}
        aria-disabled={disabled}
        onPointerDown={startDrawing}
        onPointerMove={draw}
        onPointerUp={stopDrawing}
        onPointerCancel={stopDrawing}
      />
      <div className="signature-pad-actions">
        <Button type="button" variant="ghost" disabled={disabled} onClick={clearDrawing}>
          <Eraser size={16} aria-hidden="true" />
          {t("signature.clear")}
        </Button>
        <Button
          type="button"
          disabled={disabled || !hasDrawing}
          onClick={saveDrawing}
        >
          <PenLine size={16} aria-hidden="true" />
          {t("signature.save")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={disabled}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload size={16} aria-hidden="true" />
          {t("signature.import")}
        </Button>
        <input
          ref={fileInputRef}
          className="visually-hidden"
          type="file"
          accept="image/png,image/jpeg,.png,.jpg,.jpeg"
          aria-label={t("signature.import")}
          aria-hidden="true"
          tabIndex={-1}
          onChange={importImage}
        />
      </div>
      <p className="dropzone-limit">{t("signature.importHelp")}</p>
      {error ? (
        <p className="feedback feedback-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
