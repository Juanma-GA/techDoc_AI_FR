# Proposition d'évolution du standard — analyse LLM-native de templates

Issu de la session doc-writer (export PPTX par remplissage de template).

## Contexte du retour d'expérience

Le doc-writer a d'abord essayé de détecter les zones à remplir dans un `.pptx`
via des heuristiques Python (regex `{{cle}}` / `xxx`, proximité géométrique des
labels, cellules vides de tables). Approche **déterministe, rapide, gratuite**
mais elle a échoué sur les layouts tabulaires complexes (label/valeur
côte-à-côte, cellules fusionnées, 2 tables identiques dans une slide). Résultat :
zones doublonnées, labels nonsensiques type « Entreprise / Année », LLM
produisant du garbage parce que désorienté par les descripteurs.

Le pattern qui marche : **déterministe pour la structure, LLM pour la sémantique**.

- Python (`pptx_template.py`) extrait la structure : shapes, paragraphes,
  tables, cellules, positions géométriques. Détecte les marqueurs explicites
  (`{{cle}}`, `xxx`) → zones déterministes fiables.
- Mistral (`pptx_llm_analysis.py`) reçoit un dump JSON structuré du template
  et identifie les zones implicites (cellules vides à côté de labels,
  boîtes de texte placeholder sans marqueur, layouts atypiques) avec un
  label sémantique propre.
- Résultat caché dans `Document.extracted_text` (clé `zones_v1`) pour éviter
  de re-payer à chaque ouverture du template.
- Au remplissage, **2 stratégies coexistent** :
  - Zones regex (xxx, placeholder) : substitution in-place, style préservé.
  - Zones LLM : navigation par target id (`s_<slide>_<shape_id>[_r<r>_c<c>]`)
    et écriture directe.
- **Graceful degradation** : si Mistral n'est pas configuré, on retombe sur
  les zones déterministes seules. La feature ne se bloque pas.

Validation empirique sur un template métier de dossier technique (4 slides,
78 shapes, 44 cellules de tables) :

- Heuristiques pures : 6 zones xxx slide 1 ✓, 0 zones slides 2-3 ❌
- Heuristiques + cellules vides : 50 zones, **avec doublons et labels
  cassés sur slides 2-3** ❌
- LLM-native upstream + déterministe : 6 + 20 = **26 zones précises**, labels
  propres type « Nom de l'entreprise pour cette experience professionnelle » ✓

## Proposition 1 — Nouvelle règle CLAUDE.md (entre #6 et #7)

> **6 bis. LLM-native pour la sémantique, Python pour la structure.** Pour
> tout traitement de document structuré (templates, formulaires,
> classifications layout-dependant), suivre le pattern hybride :
> extraction Python déterministe → analyse Mistral en mode JSON (avec
> `response_format`) → cache du résultat sur l'entité concernée.
> Graceful degradation obligatoire : la feature doit fonctionner (avec
> capacités réduites) sans clé Mistral. Voir la proposition d'ADR 0004 ci-dessous.

## Proposition 2 — Section STANDARD_POC.md (sous §6 LLM)

```markdown
### 6.4 Pipeline hybride pour documents structurés

Quand un POC manipule des documents dont la structure varie d'un fichier à
l'autre (templates PPTX/DOCX, formulaires, layouts métier), suivre ce pattern :

1. **Extraction Python (déterministe)** — utiliser python-pptx / python-docx /
   PyMuPDF pour produire une représentation JSON structurée du document
   (shapes, paragraphes, tables, positions). Cette étape est gratuite et
   reproductible.
2. **Analyse Mistral (sémantique)** — envoyer le dump JSON à Mistral en mode
   `response_format={"type": "json_object"}` avec un system prompt qui
   spécifie le contrat de sortie. Mistral identifie ce qui est sémantiquement
   pertinent (zones à remplir, sections à classifier, etc.).
3. **Cache du résultat** — stocker la sortie LLM sur l'entité concernée,
   versionnée par une clé `_kind: "<feature>_v1"` pour permettre l'évolution
   du schéma. Buster du cache via `?refresh=true`.
4. **Graceful degradation** — si Mistral n'est pas configuré ou échoue, la
   feature doit fonctionner avec les seules heuristiques Python (capacités
   réduites mais opérationnelles).

Référence : `apps/doc-writer/backend/app/core/pptx_llm_analysis.py`.
```

## Proposition 3 — Nouvel ADR `docs/adr/0004-llm-native-document-analysis.md`

```markdown
# ADR 0004 — Pipeline hybride déterministe + LLM pour documents structurés

- **Status** — Accepted (2026-05-20)
- **Scope** — Tout POC qui manipule des documents structurés (templates
  PPTX/DOCX, formulaires, layouts spécifiques) où la structure n'est pas
  connue à l'avance.
- **Reference** — `STANDARD_POC.md` §6.4 (à créer), `CLAUDE.md` règle 6 bis.

## Contexte

Le doc-writer devait remplir un template PowerPoint dont la structure varie :
parfois `{{cle}}` explicites, parfois `xxx` libres, parfois cellules vides
attendant un contenu, parfois layouts tabulaires complexes (label/valeur
côte-à-côte, 2 tables identiques par slide).

Deux approches testées :

1. **Heuristiques pures (regex + géométrie + cellules vides)** — rapide,
   gratuit, déterministe. Échec sur les layouts tabulaires complexes :
   doublons, labels cassés, LLM produisant du garbage en aval.
2. **LLM-native pur** — Mistral analyse le template au format brut. Impossible :
   Mistral ne lit pas le `.pptx` binaire ; il faut quand même extraire avec
   python-pptx d'abord.

## Décision

Pipeline hybride en 2 étages :

- **Étage 1 — Structure (Python déterministe)** : extraction shapes /
  paragraphes / tables / cellules / positions via python-pptx. Détection des
  marqueurs explicites (`{{cle}}`, `xxx`). Production d'un dump JSON
  structuré du document.
- **Étage 2 — Sémantique (Mistral JSON-mode)** : Mistral reçoit le dump JSON
  et identifie les zones implicites + leurs labels sémantiques. Le LLM
  comprend le layout, distingue les structurels (headers, labels) des
  fillables (valeurs).
- **Cache** : sortie LLM stockée sur l'entité (`Document.extracted_text` ici,
  `Form.metadata_json` ailleurs), versionnée (`_kind: "zones_v1"`).
- **Fallback** : si Mistral indisponible, on garde les zones déterministes
  seules. La feature reste fonctionnelle, capacités réduites.

## Conséquences

**Positives** :
- Mistral fait ce qu'il sait faire (sémantique), Python ce qu'il sait faire
  (parsing déterministe). Pas de mélange.
- Le cache amortit le coût LLM : 1 appel par upload, gratuit ensuite.
- Le fallback déterministe garantit que la feature est utilisable sans clé
  Mistral (utile en demo offline / dev).

**Négatives** :
- 1 appel Mistral supplémentaire par upload de template (~1-3s, ~2KB
  request).
- Le cache vit dans un champ texte JSON-serialized — pas idéal type-safe,
  mais évite une migration Alembic pour chaque feature.
- Le contrat JSON du LLM peut dériver si on change de modèle : à versionner
  via le `_kind`.

## Alternatives écartées

- **Tout LLM** : Mistral analyse + remplit en un seul appel. Trop gros
  contexte, hallucinations sur les ids de zones, pas robuste.
- **Tout déterministe** : impossible de coder toutes les conventions de
  layout que les utilisateurs apportent (PowerPoint laisse une infinité de
  structures). On a essayé, ça produit du garbage.
- **Marker injection** : on injecte `{{z_1}}` dans le `.pptx` après analyse
  LLM, puis on utilise le pipeline `{{cle}}` existant. Plus simple côté
  fill, mais mute le fichier source du user. Écarté pour ne pas surprendre.
```

---

## Synthèse pour transmission

Si tu veux faire évoluer le standard :

| Document | Action | Effort |
|---|---|---|
| `docs/adr/0004-llm-native-document-analysis.md` | Créer (copier la proposition 3) | 5 min |
| `STANDARD_POC.md` | Ajouter §6.4 (copier proposition 2) | 5 min |
| `CLAUDE.md` | Ajouter règle 6 bis (1 ligne) | 1 min |

Tu peux soumettre les trois ensemble en PR (`docs(standard): pipeline hybride
LLM-native pour documents structures`) — pas de code modifié dans les apps,
juste de la documentation.
