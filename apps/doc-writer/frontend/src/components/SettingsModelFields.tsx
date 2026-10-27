import { useTranslation } from "react-i18next";

type Props = {
  chatModel: string;
  setChatModel: (value: string) => void;
  embedModel: string;
  setEmbedModel: (value: string) => void;
  visionModel: string;
  setVisionModel: (value: string) => void;
  ocrModel: string;
  setOcrModel: (value: string) => void;
  transcribeModel: string;
  setTranscribeModel: (value: string) => void;
  availableModels: string[];
  transcriptionModels: string[];
};

export function SettingsModelFields({
  chatModel,
  setChatModel,
  embedModel,
  setEmbedModel,
  visionModel,
  setVisionModel,
  ocrModel,
  setOcrModel,
  transcribeModel,
  setTranscribeModel,
  availableModels,
  transcriptionModels,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      <div className="row">
        <label className="grow">
          <div className="label">{t("settings.chatModelLabel")}</div>
          <input
            className="input"
            type="text"
            list="mistral-model-options"
            value={chatModel}
            onChange={(event) => setChatModel(event.target.value)}
          />
        </label>
        <label className="grow">
          <div className="label">{t("settings.embedModelLabel")}</div>
          <input
            className="input"
            type="text"
            list="mistral-model-options"
            value={embedModel}
            onChange={(event) => setEmbedModel(event.target.value)}
          />
        </label>
      </div>
      <div className="row">
        <label className="grow">
          <div className="label">{t("settings.visionModelLabel")}</div>
          <input
            className="input"
            type="text"
            list="mistral-model-options"
            value={visionModel}
            onChange={(event) => setVisionModel(event.target.value)}
          />
          <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
            {t("settings.visionModelHint")}
          </small>
        </label>
        <label className="grow">
          <div className="label">{t("settings.ocrModelLabel")}</div>
          <input
            className="input"
            type="text"
            list="mistral-model-options"
            value={ocrModel}
            onChange={(event) => setOcrModel(event.target.value)}
          />
          <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
            {t("settings.ocrModelHint")}
          </small>
        </label>
      </div>
      {availableModels.length > 0 ? (
        <datalist id="mistral-model-options">
          {availableModels.map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
      ) : null}
      <label>
        <div className="label">{t("settings.transcribeModelLabel")}</div>
        <input
          className="input"
          type="text"
          list="transcription-model-options"
          placeholder="voxtral-..."
          value={transcribeModel}
          onChange={(event) => setTranscribeModel(event.target.value)}
        />
        {transcriptionModels.length > 0 ? (
          <datalist id="transcription-model-options">
            {transcriptionModels.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        ) : null}
        <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
          {transcriptionModels.length > 0
            ? t("settings.transcribeModelHintTested", {
                count: transcriptionModels.length,
              })
            : t("settings.transcribeModelHint")}
        </small>
      </label>
    </>
  );
}
