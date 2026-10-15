import type { TFunction } from "i18next";
import { useEffect, useState } from "react";

import type { OcrResultDto } from "../lib/api";
import { useImageBrush } from "./useImageBrush";
import { useImageView } from "./useImageView";

type ImageEditorOptions = {
  imageFile: File | null;
  imageUrl: string;
  result: OcrResultDto | null;
  t: TFunction;
};

export function useImageEditor({ imageFile, imageUrl, result, t }: ImageEditorOptions) {
  const [manualEditedImage, setManualEditedImage] = useState("");
  const previewImage = manualEditedImage || result?.edited_image || imageUrl;
  const brush = useImageBrush({
    imageFile,
    previewImage,
    hasProcessedPreview: Boolean(manualEditedImage || result?.edited_image),
    onImageEdited: setManualEditedImage,
    t,
  });
  const view = useImageView(brush.brushEnabled);

  useEffect(() => {
    setManualEditedImage("");
    brush.resetBrush();
    view.resetView();
  }, [imageUrl, result, brush.resetBrush, view.resetView]);

  const downloadName = manualEditedImage
    ? `${(result?.filename || imageFile?.name || "image").replace(/\.[^.]+$/, "")}-effacee.png`
    : result?.filename || `${imageFile?.name.replace(/\.[^.]+$/, "") || "image"}-modifiee.jpg`;

  return {
    previewImage,
    downloadName,
    manualEditedImage,
    ...brush,
    ...view,
  };
}
