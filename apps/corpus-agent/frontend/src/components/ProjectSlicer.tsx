import { useTranslation } from "react-i18next";

import type { ProjectOut } from "../lib/types";

// Slicer multi-select à pills, sémantique identique au preview (getSlicerIds) :
// value = [] signifie TOUS ; cliquer « Tous » vide la sélection ; cliquer un
// projet retire « Tous » ; si on désélectionne tout → retour à TOUS.
export type ProjectSlicerProps = {
  projects: ProjectOut[];
  value: string[];
  onChange: (next: string[]) => void;
};

export function ProjectSlicer({ projects, value, onChange }: ProjectSlicerProps) {
  const { t } = useTranslation();
  const allActive = value.length === 0;

  const toggle = (id: string) => {
    const next = value.includes(id) ? value.filter((x) => x !== id) : [...value, id];
    onChange(next);
  };

  return (
    <div className="slicer">
      <button
        type="button"
        className={allActive ? "slicer-pill active" : "slicer-pill"}
        onClick={() => onChange([])}
      >
        {t("common.allProjects")}
      </button>
      {projects.map((p) => (
        <button
          key={p.id}
          type="button"
          className={value.includes(p.id) ? "slicer-pill active" : "slicer-pill"}
          onClick={() => toggle(p.id)}
        >
          {p.name}
        </button>
      ))}
    </div>
  );
}
