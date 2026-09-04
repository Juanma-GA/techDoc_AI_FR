import { useState } from "react";
import { useTranslation } from "react-i18next";

// Editeur de nom inline reutilisable (projet, table…). Bouton « Renommer » qui
// deplie un champ ; enregistre via `onSave`. Le parent remonte le composant via
// `key` en cas de succes (le champ se referme) ; en cas d'echec `error` s'affiche
// et le champ reste ouvert.
export function RenameInline({
  current,
  pending,
  error,
  onSave,
}: {
  current: string;
  pending: boolean;
  error?: string;
  onSave: (name: string) => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<string | null>(null);

  if (draft === null) {
    return (
      <div className="row" style={{ marginTop: 10 }}>
        <button type="button" className="btn ghost" onClick={() => setDraft(current)}>
          {t("extraction.rename")}
        </button>
      </div>
    );
  }

  const submit = () => {
    const name = draft.trim();
    if (name) onSave(name);
  };

  return (
    <div style={{ marginTop: 10 }}>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <input
          className="input grow"
          value={draft}
          autoFocus
          disabled={pending}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
            if (e.key === "Escape") setDraft(null);
          }}
        />
        <button
          type="button"
          className="btn primary"
          disabled={!draft.trim() || pending}
          onClick={submit}
        >
          {t("extraction.save")}
        </button>
        <button type="button" className="btn ghost" disabled={pending} onClick={() => setDraft(null)}>
          {t("extraction.cancel")}
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
    </div>
  );
}
