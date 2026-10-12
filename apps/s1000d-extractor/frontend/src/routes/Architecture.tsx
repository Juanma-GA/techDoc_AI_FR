// Contenu FR (le preview source est FR-only).
export function Architecture() {
  const workflow = [
    "Paramètres → clé Mistral (active OCR scans + classification IA) ; validation BREX à venir.",
    "Charger → PDF/Word + version S1000D (4.1/4.2) + nature dominante → « Générer ».",
    "Découpage → choisir le niveau (chapitre/section/sous-section), revoir les Data Modules détectés.",
    "Types → corriger le type de chaque DM (descriptive / procedural / ipd).",
    "Structure → arbre par DM, trancher les nœuds ambigus (para ↔ proceduralStep).",
    "Génération → XML S1000D par DM + violations ; download par DM ou ZIP.",
  ];
  const pipeline = [
    "parse → PyMuPDF (PDF) / python-docx (Word) ; page scannée → OCR Mistral.",
    "IR canonique → arbre logique commun (sections / listes / admonitions / figures / tables).",
    "découpage (étape 1) → 1 Data Module par section/chapitre/sous-section.",
    "typage par DM (étape 2) → descriptive / procedural / ipd (heuristique + IA Mistral).",
    "résolution (étape 3) → élément S1000D selon contexte × forme ; candidats multiples si ambigu.",
    "sérialisation + validation (étape 4) → XML par DM (lxml) + XSD ; BREX à venir.",
  ];

  return (
    <>
      <div className="page-header">
        <h1>Architecture</h1>
        <p>Pipeline générique, workflow de génération et détail par étape.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Pipeline générique (3 couches indépendantes)</h2>
        <div className="grid-2">
          <div className="arch-split">
            <div className="label brand-color">CE QUI VARIE PAR DOCUMENT</div>
            <div>
              La <strong>forme d'entrée</strong> (layout PDF, styles Word) est absorbée
              par un <strong>modèle logique canonique (IR)</strong>. PDF et Word se
              normalisent dans le même IR : aucune config par document.
            </div>
          </div>
          <div className="arch-split">
            <div className="label accent-color">CE QUI VARIE PAR PROJET</div>
            <div>
              La <strong>version S1000D</strong> (4.1 / 4.2 → schémas XSD locaux) et les
              règles <strong>BREX</strong> seront prises en compte séparément. Le moteur
              de mapping, lui, ne change jamais.
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Workflow utilisateur — génération guidée</h2>
        <p className="label">
          Étapes bloquantes : on valide chacune avant la suivante. L'IA dégrossit,
          l'humain tranche.
        </p>
        <div className="arch-flow">
          {workflow.map((s, i) => (
            <div className="arch-step" key={i}>
              <span className="step-n">{i}.</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Sous le capot (pipeline par étape)</h2>
        <div className="arch-flow">
          {pipeline.map((s, i) => (
            <div className="arch-step" key={i}>
              <span className="step-n">{String.fromCharCode(65 + i)}.</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
        <div className="banner warn" style={{ marginTop: 12 }}>
          Sortie = jeu de DMs, chacun un <strong>squelette best-effort</strong> : DMC /
          applicabilité / ICN en placeholders <code>TODO</code>, à compléter par l'humain.
        </div>
      </div>
    </>
  );
}
