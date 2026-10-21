import type { TFunction } from "i18next";

export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export async function fillWithDetectedBackground(
  imageBlob: Blob,
  maskCanvas: HTMLCanvasElement,
  t: TFunction,
): Promise<string> {
  const bitmap = await createImageBitmap(imageBlob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    bitmap.close();
    throw new Error(t("image.errorPrepareImage"));
  }

  context.drawImage(bitmap, 0, 0);
  bitmap.close();
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  const maskContext = maskCanvas.getContext("2d", { willReadFrequently: true });
  if (!maskContext) throw new Error(t("image.errorReadSelection"));
  const maskData = maskContext.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
  if (maskCanvas.width !== canvas.width || maskCanvas.height !== canvas.height) {
    throw new Error(t("image.errorSelectionSize"));
  }

  let left = canvas.width;
  let top = canvas.height;
  let right = -1;
  let bottom = -1;
  for (let index = 3; index < maskData.data.length; index += 4) {
    if (maskData.data[index] === 0) continue;
    const pixel = (index - 3) / 4;
    const x = pixel % canvas.width;
    const y = Math.floor(pixel / canvas.width);
    left = Math.min(left, x);
    top = Math.min(top, y);
    right = Math.max(right, x);
    bottom = Math.max(bottom, y);
  }
  if (right < 0) throw new Error(t("image.errorEmptySelection"));

  const histograms: [Uint32Array, Uint32Array, Uint32Array] = [
    new Uint32Array(256),
    new Uint32Array(256),
    new Uint32Array(256),
  ];
  function addSample(histogram: Uint32Array, intensity: number | undefined) {
    if (intensity === undefined) return;
    const count = histogram[intensity];
    if (count !== undefined) histogram.set([count + 1], intensity);
  }
  let sampleCount = 0;
  const radius = 4;
  for (let y = Math.max(0, top - radius); y <= Math.min(canvas.height - 1, bottom + radius); y += 1) {
    for (let x = Math.max(0, left - radius); x <= Math.min(canvas.width - 1, right + radius); x += 1) {
      if (x >= left && x <= right && y >= top && y <= bottom) continue;
      const pixel = y * canvas.width + x;
      const alpha = maskData.data[pixel * 4 + 3];
      const red = imageData.data[pixel * 4];
      const green = imageData.data[pixel * 4 + 1];
      const blue = imageData.data[pixel * 4 + 2];
      if (alpha === undefined || alpha > 0 || red === undefined || green === undefined || blue === undefined) {
        continue;
      }
      addSample(histograms[0], red);
      addSample(histograms[1], green);
      addSample(histograms[2], blue);
      sampleCount += 1;
    }
  }
  if (sampleCount === 0) throw new Error(t("image.errorDetectColor"));

  function median(histogram: Uint32Array): number {
    const medianIndex = Math.floor(sampleCount / 2);
    let cumulative = 0;
    for (let value = 0; value < histogram.length; value += 1) {
      cumulative += histogram[value] ?? 0;
      if (cumulative > medianIndex) return value;
    }
    return 0;
  }
  const background: [number, number, number] = [
    median(histograms[0]),
    median(histograms[1]),
    median(histograms[2]),
  ];
  for (let index = 0; index < maskData.data.length; index += 4) {
    if (maskData.data[index + 3] === 0) continue;
    imageData.data[index] = background[0];
    imageData.data[index + 1] = background[1];
    imageData.data[index + 2] = background[2];
    imageData.data[index + 3] = 255;
  }
  context.putImageData(imageData, 0, 0);
  return canvas.toDataURL("image/png");
}
