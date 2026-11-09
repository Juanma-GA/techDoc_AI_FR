# Corpus Agent Evaluation Framework

**Status:** Initial proposal. Domain targets and candidate thresholds require
validation with business stakeholders.

## Purpose

Evaluate whether Corpus Agent reliably turns documentary information into
traceable, useful findings and review actions. The framework must support
different document-management and technical-documentation contexts without
assuming that every target capability is already implemented.

The first domain packs should cover **testability** and **industrial
maintenance**. The common evaluation core should also be applicable to GED/EDM
and other technical-documentation domains.

## Current foundation and boundaries

The current application already provides local folder synchronization,
document versions with SHA-256 fingerprints, project reference/BASL files,
editable checklist rules, analysis runs, findings linked to file versions and
runs, reviewer statuses and feedback, and chat citations.

Analysis combines deterministic reference/BASL cross-checks with an
LLM-driven custom checklist. The framework must distinguish their coverage
and identify checklist runs without an available LLM, active rules, or usable
extracted content. It must not treat an empty finding list as proof of
compliance.

Generic enterprise connectors, cross-system workflows, and autonomous writes
are future capabilities, not assumptions of this evaluation baseline.

## Shared evaluation model

Each evaluation scenario is a versioned set of source documents and expected
outcomes. A scenario should include:

- Domain pack and scenario identifier.
- Source document identifiers and versions.
- The relevant rule or checklist version.
- Expected finding, expected no-finding, or expected abstention.
- Expected category and severity where applicable.
- Verifiable evidence text and its location (page, section, sheet, cell, or
  other domain-appropriate locator).
- Expected reviewer action or resolution outcome where applicable.

Include clear positive cases, compliant negative cases, cross-document
inconsistencies, and ambiguous or incomplete evidence. Keep scenarios grouped
by project or corpus when creating development and holdout sets to reduce
content leakage.

## Domain packs

Domain packs reuse the shared scenario and scoring model but provide
domain-specific document types, relationships, checks, annotations, and
business outcomes.

| Pack | Example evaluation questions |
|---|---|
| GED / document management | Are required metadata and lifecycle states present? Are duplicate or superseded versions identified? Are document relationships and approvals traceable? |
| Technical documentation | Are references and statements consistent across revisions and related documents? Can a change be traced to affected content? |
| Testability | Can each requirement be linked to suitable test cases and results? Are gaps, orphan tests, and unverified changes identified with evidence? |
| Industrial maintenance | Are maintenance instructions, tasks, parts, tooling, and reference data consistent and complete for the selected procedure or equipment? |

These are evaluation targets, not claims that Corpus Agent currently supports
all of these checks or source integrations. Start with a small but diverse set
of scenarios per seed pack, including positive, compliant, ambiguous, and
cross-document cases. Treat early metrics as exploratory until the sample is
large enough to support meaningful comparisons.

The initial synthetic benchmark contains two scenarios in each of the four
domain packs. It is an executable scoring seed, not a statistically
representative validation set or evidence that the listed checks are already
implemented.

## Evaluation dimensions

### Quality

- Finding precision, recall, and F1, calculated with one-to-one matching
  between generated and expected findings.
- Breakdown by domain, category, severity, and document type.
- Separate counts for false positives, missed findings, and findings with
  incorrect severity or non-matching evidence.
- Correct abstention when evidence is missing or ambiguous.

### Evidence and traceability

- Percentage of findings linked to the exact source document version and
  analysis run.
- Percentage whose quoted evidence can be verified in that exact version.
- Exact evidence agreement against the reviewed benchmark annotation.
- Accuracy of page, section, sheet, cell, or other location where available.
- Percentage with enough provenance to reproduce the decision: dataset
  version, rule/checklist version, model and prompt configuration, and
  reviewer outcome.
- Unsupported-finding rate, reported separately from ordinary false
  positives.

### Reliability

- Source parsing and usable-text coverage.
- Indexing and analysis completion rates, with explicit skipped/error states.
- Repeat-run agreement on the same scenario and configuration.
- Correct degraded behavior when the LLM, embeddings, or a source is
  unavailable.
- False-green count: scenarios reported as verified/compliant when required
  checks did not actually run.

The current analysis response reports selected, parsed, empty, unversioned,
and failed files; successful file and rule evaluations; LLM failures; and a
`verified`, `partial`, or `not_verified` status. Only a fully covered run may
show that no anomaly was found among the checks executed. RAG indexing
failures are reported separately because indexing is not itself a checklist
verification. Runs also retain the active rule-set SHA-256, prompt version,
and configured LLM model in their summary; anomaly records expose the exact
source-version hash and analysis-run ID alongside their evidence in the
reviewer view and CSV export.

### Business value

- Reviewer time per corpus or scenario compared with the current manual
  baseline.
- Recommendation acceptance, rejection, and modification rates.
- Time from finding to validated resolution.
- Recurrence rate after a finding is marked fixed and the relevant content is
  re-analyzed.

## Candidate initial targets

Treat these as hypotheses for the first pilot, not release gates. Calibrate
them with domain owners after measuring the baseline:

- At least 0.85 precision and 0.80 recall for in-scope findings, reported
  separately for each domain pack.
- At least 95% of generated findings have evidence verifiable against the
  exact source version.
- Zero false-green outcomes on negative-control scenarios where a required
  rule, source, or LLM evaluation is unavailable.
- At least 20% reduction in median review time without reducing finding
  quality.
- Set a repeat-run agreement target after measuring the variability of the
  chosen model and prompt; report the observed rate on every evaluation run.

Do not aggregate the domain packs into a single score that can hide a weak
result in one context. Report per-domain metrics and sample counts alongside
every score.

## Quick wins

1. **Make analysis coverage visible.** Record and expose counts for source
   files, parse failures or empty text, indexed files/chunks, active rules, and
   whether LLM evaluation actually ran. Do not label an unevaluated scenario
   as compliant.
2. **Create a small gold set.** Add synthetic, version-controlled scenarios
   for testability and industrial maintenance, including expected findings,
   compliant cases, and ambiguous cases. Use real business documents only
   after explicit authorization and controlled anonymization.
3. **Automate deterministic scoring.** `backend/app/core/evaluation.py`
   scores finding precision/recall, exact evidence support, and abstention;
   its dataset scorer accepts dataset-version and run metadata for reproducible
   reports. The fixture tests run without an API key or network access. Keep
   live LLM evaluation opt-in.
4. **Strengthen finding evidence.** Findings now store the quoted source
   evidence separately from location and retain the file-version and
   analysis-run links. Domain-specific page, section, sheet, or cell locators
   remain a follow-up when parsers can provide them reliably; retain reviewer
   feedback as an evaluation outcome.
5. **Expand by domain pack.** Add GED/EDM and further technical-documentation
   contexts only when a domain owner, representative scenarios, and expected
   outcomes are available.

## Dataset and run controls

- Use synthetic fixtures by default; do not read application databases,
  uploaded documents, or user storage to build the benchmark.
- Have a domain reviewer validate expected findings and evidence. Record
  unresolved annotation disagreements rather than forcing a single answer.
- Version each domain pack and keep a holdout set for comparisons.
- The existing Demo Mode remains a synthetic maintenance-corpus showcase. Its
  seeded anomaly trend is illustrative, not a ground-truth benchmark; the
  versioned evaluation fixtures are kept separate to avoid conflating the two.
- Store evaluation results with the code revision, dataset version, domain
  pack, model/prompt/checklist versions, run timestamp, metrics, and known
  limitations.
- Keep deterministic unit/regression tests separate from opt-in live-model
  experiments; never make normal CI depend on an external LLM service.
