import type { TFunction } from "i18next";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { MAX_UPLOAD_BYTES } from "../lib/image-processing";
import { useExcelMapping } from "./useExcelMapping";

const SUPPORTED_IMAGE_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/bmp",
  "image/tiff",
  "image/x-tiff",
]);

export type ReplacementPair = {
  id: number;
  reference: string;
  replacement: string;
};

export function useImageReplace(t: TFunction) {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState("");
  const [replacementPairs, setReplacementPairs] = useState<ReplacementPair[]>([]);
  const [result, setResult] = useState<OcrResultDto | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const nextPairId = useRef(0);
  const excel = useExcelMapping(t);

  useEffect(() => {
    if (!imageFile) {
      setImageUrl("");
      return undefined;
    }
    const url = URL.createObjectURL(imageFile);
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  useEffect(() => {
    setResult(null);
  }, [
    excel.excelFile,
    excel.excelSheet,
    excel.excelReferenceColumn,
    excel.excelReplacementColumn,
    excel.excelIcnColumn,
    excel.excelPieceColumn,
    excel.excelPieceRow,
  ]);

  function chooseImage(files: File[]) {
    const nextFile = files[0];
    if (!nextFile) return;
    if (!SUPPORTED_IMAGE_TYPES.has(nextFile.type)) {
      setError(t("image.errorImageType"));
      return;
    }
    if (nextFile.size > MAX_UPLOAD_BYTES) {
      setError(t("image.errorImageSize"));
      return;
    }
    setImageFile(nextFile);
    setResult(null);
    setError("");
  }

  function updatePair(id: number, field: "reference" | "replacement", value: string) {
    setReplacementPairs((current) =>
      current.map((pair) => (pair.id === id ? { ...pair, [field]: value } : pair)),
    );
  }

  function addPair() {
    const id = nextPairId.current++;
    setReplacementPairs((current) => [...current, { id, reference: "", replacement: "" }]);
  }

  function removePair(id: number) {
    setReplacementPairs((current) => current.filter((pair) => pair.id !== id));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!imageFile) return;

    const replacements = replacementPairs
      .map(({ reference, replacement }) => ({
        reference: reference.trim(),
        replacement: replacement.trim(),
      }))
      .filter(({ reference, replacement }) => reference || replacement);
    if (replacements.some(({ reference, replacement }) => !reference || !replacement)) {
      setError(t("image.errorPairIncomplete"));
      return;
    }
    const excelReplacements = excel.excelPairs.map(({ reference, replacement }) => ({
      reference: reference.trim(),
      replacement: replacement.trim(),
    }));
    if (excelReplacements.some(({ reference, replacement }) => !reference || !replacement)) {
      setError(t("image.errorPairIncomplete"));
      return;
    }
    if (excel.excelFile && !excel.excelSelectionReady) {
      setError(t("image.errorExcelSelection"));
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    const formData = new FormData();
    formData.append("image", imageFile);
    formData.append("replacement_pairs", JSON.stringify(replacements));
    if (excel.excelFile) {
      formData.append("workbook", excel.excelFile);
      formData.append("excel_sheet", excel.excelSheet);
      formData.append("excel_reference_column", excel.excelReferenceColumn);
      formData.append("excel_replacement_column", excel.excelReplacementColumn);
      formData.append("excel_icn_column", excel.excelIcnColumn);
      formData.append("excel_piece_column", excel.excelPieceColumn);
      formData.append("excel_piece_row", excel.excelPieceRow);
      formData.append("excel_replacement_pairs", JSON.stringify(excelReplacements));
    }

    try {
      setResult(await imageReplaceApi.runOcr(formData));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("image.errorGeneric"));
    } finally {
      setLoading(false);
    }
  }

  return {
    ...excel,
    imageFile,
    imageUrl,
    replacementPairs,
    result,
    error,
    loading,
    chooseImage,
    updatePair,
    addPair,
    removePair,
    submit,
    setError,
    setResult,
  };
}
