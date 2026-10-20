import { Button } from "@internal/ui";
import { Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { errorText } from "../../lib/api";
import { convertApi, saveResponse } from "../../lib/flowApi";
import type { FlowGraph } from "../../types/flow";

export function ExportBar({ graph }: { graph: FlowGraph }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const formats = useQuery({ queryKey: ["formats"], queryFn: convertApi.formats, staleTime: Infinity });

  const download = async (fmt: string, ext: string) => {
    setBusy(fmt);
    setError(null);
    try {
      const response = await convertApi.render(graph, fmt);
      await saveResponse(response, `logigramme${ext}`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2" data-testid="export-bar">
        {(formats.data ?? []).map((f) => (
          <Button
            key={f.format}
            size="sm"
            variant="secondary"
            disabled={busy !== null}
            title={t(`formats.${f.format}`, { defaultValue: f.format })}
            onClick={() => void download(f.format, f.extension)}
          >
            <Download className="mr-1 h-4 w-4" aria-hidden />
            {f.format.toUpperCase()}
          </Button>
        ))}
      </div>
      {error && (
        <div className="text-sm text-danger" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
