import { useId, useState, type FormEvent } from "react";
import { FileText, Scissors, Trash2, X } from "lucide-react";

import { processPDF } from "../../shared/api";
import { Button } from "../../shared/components/Button";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";

type PageSelectionMode = "extract" | "delete";

const modeConfiguration = {
  extract: {
    endpoint: "extract",
    outputName: "extract.pdf",
    action: "Extraire les pages",
    heading: "Choisir les pages à conserver",
    description: "Le nouveau PDF ne contiendra que les pages indiquées.",
    icon: Scissors,
  },
  delete: {
    endpoint: "delete",
    outputName: "trimmed.pdf",
    action: "Supprimer les pages",
    heading: "Choisir les pages à retirer",
    description: "Le PDF doit conserver au moins une page.",
    icon: Trash2,
  },
} as const;

type PageSelectionToolProps = {
  mode: PageSelectionMode;
};

export function PageSelectionTool({ mode }: PageSelectionToolProps) {
  const config = modeConfiguration[mode];
  const Icon = config.icon;
  const pageInputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [selection, setSelection] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError("Sélectionnez un fichier PDF.");
      return;
    }
    if (!selection.trim()) {
      setError("Indiquez les pages à traiter.");
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("pages", selection);
    try {
      await processPDF(config.endpoint, data, config.outputName);
      setSuccess(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Le traitement des pages a échoué.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <section className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>Choisir le PDF</h2>
            <p>Un seul document par opération.</p>
          </div>
        </div>
        <FileDropzone
          disabled={working}
          onFiles={(incoming) => {
            setFile(incoming[0] ?? null);
            setSuccess(false);
          }}
          onError={setError}
        />
        {file ? (
          <div className="selected-file">
            <span className="file-row-icon">
              <FileText size={17} aria-hidden="true" />
            </span>
            <span className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size)}</span>
            </span>
            <Button
              variant="ghost"
              className="icon-button remove-button"
              disabled={working}
              onClick={() => {
                setFile(null);
                setSelection("");
              }}
              aria-label="Retirer le fichier"
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
        <p className="privacy-hint">
          Les fichiers sont transmis au serveur local pour être traités, puis les temporaires sont
          supprimés.
        </p>
      </section>

      <section className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{config.heading}</h2>
            <p>{config.description}</p>
          </div>
        </div>
        <label className="field-label" htmlFor={pageInputId}>
          Pages
        </label>
        <input
          id={pageInputId}
          className="text-input page-range-input"
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder="Ex. 1-5, 8, 10-12"
          value={selection}
          disabled={working}
          onChange={(event) => {
            setSelection(event.currentTarget.value);
            setSuccess(false);
          }}
          aria-describedby={`${pageInputId}-help`}
        />
        <p className="input-help" id={`${pageInputId}-help`}>
          Numéros séparés par des virgules ou plages avec un tiret, par exemple 1,3,7 ou 2-4,8.
        </p>
        {mode === "delete" ? (
          <p className="warning-note">Toutes les pages ne peuvent pas être supprimées.</p>
        ) : null}
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <strong>{config.outputName}</strong>
            <small>{mode === "extract" ? "Pages extraites" : "Pages supprimées"}</small>
          </span>
        </div>
        <Button
          type="submit"
          disabled={working || !file || !selection.trim()}
          className="action-button"
        >
          {working ? <span className="spinner" aria-hidden="true" /> : <Icon size={18} />}
          {working ? "Traitement en cours…" : config.action}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              Le fichier {config.outputName} a été téléchargé.
            </p>
          ) : null}
        </div>
      </section>
    </form>
  );
}
