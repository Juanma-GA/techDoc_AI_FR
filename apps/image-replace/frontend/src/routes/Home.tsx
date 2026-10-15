import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ImageInputPanel } from "../components/ImageInputPanel";
import { ImagePreview } from "../components/ImagePreview";
import { OcrResults } from "../components/OcrResults";
import { useImageReplace } from "../hooks/useImageReplace";

export function Home() {
  const { t } = useTranslation();
  const workflow = useImageReplace(t);
  const [retouching, setRetouching] = useState(false);
  const busy = workflow.loading || workflow.excelLoading || retouching;

  return (
    <div className="space-y-4">
      <header className="page-header">
        <div>
          <h1>{t("home.title")}</h1>
          <p>{t("home.subtitle")}</p>
        </div>
      </header>

      <form
        onSubmit={workflow.submit}
        className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(20rem,0.82fr)_minmax(0,1.18fr)]"
      >
        <ImageInputPanel workflow={workflow} disabled={busy} t={t} />
        <div className="min-w-0 space-y-4">
          <ImagePreview
            imageFile={workflow.imageFile}
            imageUrl={workflow.imageUrl}
            result={workflow.result}
            disabled={busy}
            onInpaintingChange={setRetouching}
            t={t}
          />
          <OcrResults result={workflow.result} t={t} />
        </div>
      </form>
    </div>
  );
}
