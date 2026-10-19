import type { TFunction } from "i18next";
import { useEffect } from "react";

import { useImageBrush } from "./useImageBrush";
import { useImageView } from "./useImageView";

type ImageEditorOptions = {
  imageFile: File | null;
  imageUrl: string;
  manuallyEdited: boolean;
  onImageEdited: (image: string, mode: "lama" | "color") => void;
  onInpaintingChange: (busy: boolean) => void;
  t: TFunction;
};

export function useImageEditor({
  imageFile, imageUrl, manuallyEdited, onImageEdited, onInpaintingChange, t,
}: ImageEditorOptions) {
  const previewImage = imageUrl;
  const brush = useImageBrush({
    imageFile,
    onImageEdited,
    onBusyChange: onInpaintingChange,
    t,
  });
  const view = useImageView(brush.brushEnabled);

  useEffect(() => {
    brush.resetBrush();
    view.resetView();
  }, [imageUrl, brush.resetBrush, view.resetView]);

  return {
    previewImage,
    manualEditedImage: manuallyEdited ? imageUrl : "",
    ...brush,
    ...view,
  };
}
