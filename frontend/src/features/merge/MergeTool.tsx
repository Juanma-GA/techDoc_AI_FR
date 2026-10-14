import { useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, Combine, FileText, X } from "lucide-react";

import { processPDF } from "../../shared/api";
import { Button } from "../../shared/components/Button";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";

export function MergeTool() {
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);

  const moveFile = (index: number, offset: -1 | 1) => {
    setFiles((current) => {
      const target = index + offset;
      if (target < 0 || target >= current.length) {
        return current;
      }
      const updated = [...current];
      [updated[index], updated[target]] = [updated[target], updated[index]];
      return updated;
    });
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (files.length < 2) {
      setError("Ajoutez au moins deux fichiers PDF à fusionner.");
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    for (const file of files) {
      data.append("files", file, file.name);
    }
    try {
      await processPDF("merge", data, "merged.pdf");
      setSuccess(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "La fusion a échoué.");
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
            <h2>Ajouter les PDF</h2>
            <p>Les documents seront assemblés dans l'ordre affiché.</p>
          </div>
        </div>
        <FileDropzone
          multiple
          disabled={working}
          onFiles={(incoming) => setFiles((current) => [...current, ...incoming])}
          onError={setError}
          label="Déposez plusieurs PDF ici"
          description="Vous pouvez aussi cliquer pour parcourir les fichiers"
        />
        {files.length > 0 ? (
          <ol className="file-list" aria-label="Ordre des fichiers à fusionner">
            {files.map((file, index) => (
              <li className="file-row" key={`${file.name}-${file.lastModified}-${index}`}>
                <span className="file-order">{index + 1}</span>
                <span className="file-row-icon">
                  <FileText size={17} aria-hidden="true" />
                </span>
                <span className="file-details">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">{formatFileSize(file.size)}</span>
                </span>
                <div className="file-actions">
                  <Button
                    variant="ghost"
                    className="icon-button"
                    disabled={index === 0 || working}
                    onClick={() => moveFile(index, -1)}
                    aria-label={`Déplacer ${file.name} vers le haut`}
                  >
                    <ArrowUp size={16} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button"
                    disabled={index === files.length - 1 || working}
                    onClick={() => moveFile(index, 1)}
                    aria-label={`Déplacer ${file.name} vers le bas`}
                  >
                    <ArrowDown size={16} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button remove-button"
                    disabled={working}
                    onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
                    aria-label={`Retirer ${file.name}`}
                  >
                    <X size={16} aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
        <p className="privacy-hint">
          Les fichiers sont envoyés au serveur local uniquement lors de la fusion.
        </p>
      </section>

      <section className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>Créer le document</h2>
            <p>Un PDF unique sera téléchargé automatiquement.</p>
          </div>
        </div>
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <strong>merged.pdf</strong>
            <small>Document fusionné</small>
          </span>
        </div>
        <Button type="submit" disabled={working || files.length < 2} className="action-button">
          {working ? <span className="spinner" aria-hidden="true" /> : <Combine size={18} />}
          {working ? "Fusion en cours…" : "Fusionner"}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              Le fichier merged.pdf a été téléchargé.
            </p>
          ) : null}
        </div>
      </section>
    </form>
  );
}
