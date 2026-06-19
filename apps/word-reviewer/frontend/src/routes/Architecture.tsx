export function Architecture() {
  const steps = [
    "Upload .docx / .zip → parsing en blocs (paragraphes, cellules, en-têtes/pieds) + lecture du suivi de modifications.",
    "Reconnaissance des zones (footer, Highlights, Fiche suiveuse, LEP).",
    "Moteur : règles déterministes (regex/zone/style) + structurelles + révision + LLM (llm_nl).",
    "Fiabilisation : vérif adversariale + routage par confiance + exclusions (feedback).",
    "Revue : appliquer les corrections (versions + rollback) ou cocher les items manuels.",
    "Export du .docx corrigé (ou .zip du lot).",
  ];
  return (
    <>
      <div className="page-header">
        <h1>Architecture</h1>
        <p>Pipeline et stack.</p>
      </div>
      <div className="card">
        <h2 className="card-title">Pipeline</h2>
        <div className="arch-flow">
          {steps.map((s, i) => (
            <div className="arch-step" key={i}>
              <span className="step-n">{i + 1}.</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <div className="grid-2">
          <div className="arch-split">
            <div className="label brand-color">BACKEND</div>
            <div>
              FastAPI /api/v1 · SQLAlchemy 2 + SQLite + Alembic · python-docx + lxml ·
              openpyxl · Mistral via httpx (SSE).
            </div>
          </div>
          <div className="arch-split">
            <div className="label accent-color">UI</div>
            <div>
              React 18 + TypeScript + Vite + Tailwind + i18next + TanStack Query, servie par
              le backend.
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
