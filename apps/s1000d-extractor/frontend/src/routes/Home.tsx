import { useQuery } from "@tanstack/react-query";

import { healthApi, type HealthDto } from "../lib/api";

// Contenu FR (le preview source est FR-only).
export function Home() {
  const { data: health } = useQuery<HealthDto>({
    queryKey: ["health"],
    queryFn: healthApi.read,
  });

  return (
    <>
      <div className="page-header">
        <h1>Accueil</h1>
        <p>Migration de documentation legacy vers S1000D.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Migration legacy vers S1000D</h2>
        <p>
          Cet outil extrait un <strong>squelette structurel S1000D</strong> à partir
          d'un PDF natif ou d'un fichier Word, pour amorcer la conversion de
          documentation ancienne.
        </p>
        <p>
          Principe : le type d'élément S1000D dépend du <strong>contexte</strong> (une
          liste à puces devient <code>randomList</code> en zone descriptive,{" "}
          <code>proceduralStep</code> en procédure), pas de la forme. L'outil classe le
          contexte, propose le mapping et signale les cas ambigus pour revue humaine.
        </p>
        <div className="banner warn">
          <strong>Best-effort.</strong> La sortie n'est PAS un Data Module valide : DMC,
          BREX, applicabilité, SNS et ICN ne sont pas récupérables d'un PDF et restent à
          compléter par un humain.
        </div>
        <div className="banner">
          Statut backend :{" "}
          {health ? (
            <span className="badge ok">{health.status}</span>
          ) : (
            <span className="badge warn">INCONNU</span>
          )}
          {health ? (
            <>
              {" · "}LLM : <span className="badge">{health.llm}</span>
              {" · "}version : <code>{health.version}</code>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}
