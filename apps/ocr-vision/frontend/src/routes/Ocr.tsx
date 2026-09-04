import { useState } from "react";
import { useTranslation } from "react-i18next";

import { visionApi, type VisionResultDto } from "../lib/api";

// Onglet OCR / Vision : upload image/PDF + prompt optionnel -> /vision/test.
export function Ocr() {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState("");
  const [result, setResult] = useState<VisionResultDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!file) {
      setMsg(t("ocr.noFile"));
      return;
    }
    setRunning(true);
    setMsg(t("ocr.running"));
    setResult(null);
    setError(null);
    try {
      const out = await visionApi.test(file, prompt);
      setMsg(out.warning ? t("ocr.warningPrefix") + out.warning : "");
      setResult(out);
    } catch (e) {
      setMsg("");
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("routes.ocr.title")}</h1>
        <p>{t("routes.ocr.sub")}</p>
      </div>

      <div className="card">
        <div className="card-title">{t("ocr.cardTitle")}</div>
        <div className="banner">{t("ocr.banner")}</div>
        <input
          type="file"
          className="input"
          accept="image/*,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <div className="label" style={{ margin: "10px 0 4px" }}>
          {t("ocr.promptLabel")}
        </div>
        <textarea
          className="input"
          rows={3}
          value={prompt}
          placeholder={t("ocr.promptPlaceholder")}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div style={{ marginTop: 10 }}>
          <button
            type="button"
            className="btn primary"
            disabled={running}
            onClick={() => void run()}
          >
            {t("ocr.run")}
          </button>{" "}
          <span className="label">{msg}</span>
        </div>

        {error ? <div className="error">{error}</div> : null}

        {result ? (
          <div style={{ marginTop: 14 }}>
            <div className="card-title">{t("ocr.ocrResultTitle")}</div>
            <pre style={{ whiteSpace: "pre-wrap" }}>
              {result.ocr_text || t("ocr.ocrEmpty")}
            </pre>
            <div className="card-title" style={{ marginTop: 12 }}>
              {t("ocr.descResultTitle")}
            </div>
            <div>{result.description || t("ocr.descEmpty")}</div>
          </div>
        ) : null}
      </div>
    </>
  );
}
