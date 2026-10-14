import {
  ArrowRight,
  Combine,
  Grip,
  Scissors,
  Trash2,
  type LucideIcon,
} from "lucide-react";

export type ToolId = "merge" | "extract" | "delete" | "reorder";

type HomePageProps = {
  onSelectTool: (tool: ToolId) => void;
};

const tools: {
  id: ToolId;
  title: string;
  description: string;
  icon: LucideIcon;
  className: string;
}[] = [
  {
    id: "merge",
    title: "Fusionner PDF",
    description: "Combinez plusieurs documents dans un seul fichier PDF.",
    icon: Combine,
    className: "tool-icon-blue",
  },
  {
    id: "extract",
    title: "Extraire des pages",
    description: "Conservez uniquement les pages dont vous avez besoin.",
    icon: Scissors,
    className: "tool-icon-violet",
  },
  {
    id: "delete",
    title: "Supprimer des pages",
    description: "Retirez les pages inutiles d'un document PDF.",
    icon: Trash2,
    className: "tool-icon-rose",
  },
  {
    id: "reorder",
    title: "Réorganiser des pages",
    description: "Glissez les miniatures pour modifier l'ordre des pages.",
    icon: Grip,
    className: "tool-icon-green",
  },
];

export function HomePage({ onSelectTool }: HomePageProps) {
  return (
    <section className="home-page">
      <div className="home-intro">
        <p className="eyebrow">SIMPLE · RAPIDE · LOCAL</p>
        <h1>Les outils PDF essentiels.</h1>
        <p>
          Préparez vos documents directement sur cette machine. Aucun compte, aucune base de
          données et aucun stockage permanent.
        </p>
      </div>

      <div className="tool-grid">
        {tools.map(({ id, title, description, icon: Icon, className }) => (
          <article className="tool-card" key={id}>
            <div className={`tool-card-icon ${className}`}>
              <Icon size={23} strokeWidth={1.9} aria-hidden="true" />
            </div>
            <h2>{title}</h2>
            <p>{description}</p>
            <button className="tool-card-action" type="button" onClick={() => onSelectTool(id)}>
              Ouvrir l'outil
              <ArrowRight size={16} aria-hidden="true" />
            </button>
          </article>
        ))}
      </div>

      <div className="privacy-note">
        <span className="privacy-dot" aria-hidden="true" />
        Les fichiers de travail sont temporaires et supprimés à la fin de chaque opération.
      </div>
    </section>
  );
}
