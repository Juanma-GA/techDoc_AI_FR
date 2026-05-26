"""S1000D catalog — versions 5.0 and 6.0.

S1000D est avant tout une **spécification XML/SGML** : son livrable principal
ce sont les DTD/XSD pour les Data Modules. Les règles éditoriales sont
exprimées comme des conventions sur les balises (`<warning>`, `<caution>`,
`<closeRqmts>`, `<preliminaryRqmts>`, `<proceduralStep>`, `<applicability>`,
`<dmTitle>`, `<figure>` + `<title>`, etc.) et publiées dans BREX (Business
Rules Exchange) — un Data Module qui valide la conformité d'autres DM.

Le PDF Reviewer n'analyse pas le XML source mais le **rendu PDF** publié.
Chaque règle ci-dessous indique entre crochets dans la description la
balise S1000D dont elle vérifie le rendu (« balise : <warning> »).

Pour les règles de style rédactionnel (phrases courtes, voix active,
gérondif, vocabulaire approuvé), voir la norme distincte ASD-STE100.
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_S1000D_WARNING = StandardRule(
    code="S1000D_WARNING_FORMAT",
    title="Format des avertissements",
    description=(
        "S1000D §4.2 — balise : `<warning>` / `<caution>`. Les notices "
        "WARNING / CAUTION / DANGER doivent apparaître sur une ligne "
        "dédiée, en MAJUSCULES, avant la procédure concernée. Un "
        "avertissement inline dans une phrase indique un usage incorrect "
        "de la balise (texte hors `<warning>`)."
    ),
    kind="regex_replace",
    severity="warning",
    pattern=r"(?<![A-Z\n])\b(warning|caution|danger)\s*[:,]",
    replacement=r"\1",
    message="Avertissement inline — déplacer dans une balise <warning> rendue sur ligne dédiée.",
)

_S1000D_DOUBLE_SPACE = StandardRule(
    code="S1000D_DOUBLE_SPACE",
    title="Espaces doubles",
    description=(
        "Convention typographique S1000D — un seul espace après la "
        "ponctuation. Plusieurs espaces consécutifs trahissent un mauvais "
        "rendu PCDATA ou un copier-coller depuis un éditeur WYSIWYG."
    ),
    kind="regex_replace",
    severity="info",
    pattern=r"  +",
    replacement=" ",
    message="Double espace — un seul espace après la ponctuation S1000D.",
)

_S1000D_DMC_FORMAT = StandardRule(
    code="S1000D_DMC_FORMAT",
    title="Data Module Code (DMC) bien formé",
    description=(
        "S1000D §3 — balise : `<dmIdent><dmCode>`. La référence DMC suit "
        "obligatoirement le format MI-AC-AN-SY-SS-SU-DC-IC "
        "(modelIdent, system, subSystem, subSubSystem, assyCode, "
        "disassyCode, infoCode, itemLocation)."
    ),
    kind="regex_flag",
    severity="warning",
    pattern=r"\bDMC[-\s][A-Z0-9]{2,5}-[A-Z]-\d{2}-\d{2}-\d{2}-\d{2}[A-Z]-\d{3}[A-Z]-[A-Z]\b",
    message="Référence DMC — vérifier la conformité au format S1000D §3.",
)

_S1000D_APPLICABILITY = StandardRule(
    code="S1000D_APPLICABILITY",
    title="Statement d'applicabilité présent",
    description=(
        "S1000D §6.1 — balise : `<applic>` / `<applicCrossRefGroupRef>`. "
        "Tout Data Module doit déclarer son applicabilité (modèles, "
        "configurations, MSN concernés). Le rendu PDF contient « "
        "Applicability », « Applicable to » ou « Effectivity » au début "
        "du document."
    ),
    kind="section_required",
    severity="error",
    pattern="Applicability|Applicable to|Effectivity|Applicabilité",
    message="Section <applicability> absente dans le document.",
)

_S1000D_DM_TITLE = StandardRule(
    code="S1000D_DM_TITLE",
    title="dmTitle structuré (techName + infoName)",
    description=(
        "S1000D §3.4 — balise : `<dmTitle><techName>` + `<infoName>`. "
        "Le titre du Data Module doit combiner un nom technique (sujet) "
        "et un nom d'information (action / type). Un titre nu sans "
        "structuration trahit une balise `<title>` plate au lieu de "
        "`<dmTitle>`."
    ),
    kind="regex_flag",
    severity="info",
    pattern=r"^\s*[A-Z][A-Za-zÀ-ÿ\s]{3,40}\s*[—\-–]\s*[A-Za-zÀ-ÿ\s]{3,40}\s*$",
    message="dmTitle — vérifier la structure techName + infoName.",
)

_S1000D_FIGURE_CAPTION = StandardRule(
    code="S1000D_FIGURE_CAPTION",
    title="Figure suivie d'une caption",
    description=(
        "S1000D §5.2 — balise : `<figure>` doit contenir `<title>`. Le "
        "rendu PDF affiche « Figure N » ou « Fig. N » suivi d'une "
        "courte description. Une mention « Figure N » sans titre derrière "
        "indique un `<figure>` sans `<title>`."
    ),
    kind="regex_flag",
    severity="warning",
    pattern=r"\b(?:Figure|Fig\.)\s+\d+\s*(?:$|[\.\n])",
    message="Figure sans caption — balise <figure> sans <title> ?",
)

_PROC_VERB_INFINITIVE = StandardRule(
    code="PROC_STEP_VERB",
    title="Étape procédurale = verbe d'action",
    description=(
        "S1000D §4.5 — balise : `<proceduralStep>`. Chaque étape "
        "numérotée doit commencer par un verbe d'action à l'impératif/"
        "infinitif (« Retirer », « Vérifier », « Remove »). Une phrase "
        "nominale ou un sujet explicite indique un usage incorrect de "
        "`<proceduralStep>` (devrait être `<para>` ou `<note>`)."
    ),
    kind="step_pattern",
    severity="warning",
    pattern=r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b|[A-Z][a-z]{3,}(?:\s|$))",
    message="<proceduralStep> doit commencer par un verbe d'action.",
    example_invalid="1. Le panneau est retiré.",
    example_valid="1. Retirer le panneau.",
)

_PROC_PRELIM_TASKS = StandardRule(
    code="PROC_PRELIM_TASKS",
    title="Bloc <preliminaryRqmts> présent",
    description=(
        "S1000D §4.5 — balise : `<preliminaryRqmts>`. Toute procédure de "
        "maintenance corrective doit déclarer ses prérequis "
        "(consignation, mise en sécurité, accès) AVANT les étapes "
        "principales. Le rendu PDF contient une section « Preliminary "
        "requirements » ou « Tâches préliminaires »."
    ),
    kind="section_required",
    severity="warning",
    pattern="Preliminary requirements|Preliminary tasks|Tâches préliminaires|Préliminaires",
    message="Balise <preliminaryRqmts> absente dans la procédure.",
)

_PROC_POST_TASKS = StandardRule(
    code="PROC_POST_TASKS",
    title="Bloc <closeRqmts> présent",
    description=(
        "S1000D §4.5 — balise : `<closeRqmts>`. Toute procédure se "
        "termine par une section de restauration (déconsignation, test "
        "fonctionnel, remise en service). Rendu PDF : « Close out », "
        "« Restoration », « Tâches post-maintenance »."
    ),
    kind="section_required",
    severity="warning",
    pattern="Close out|Closing tasks|Restoration|Tâches post-maintenance|Post-maintenance",
    message="Balise <closeRqmts> absente — la procédure n'est pas fermée.",
)


_RULES_60 = [
    _S1000D_WARNING,
    _S1000D_DOUBLE_SPACE,
    _S1000D_DMC_FORMAT,
    _S1000D_APPLICABILITY,
    _S1000D_DM_TITLE,
    _S1000D_FIGURE_CAPTION,
    _PROC_VERB_INFINITIVE,
    _PROC_PRELIM_TASKS,
    _PROC_POST_TASKS,
]


# S1000D 5.0 — DMC nouveau format et PROC_STEP_VERB explicite sont apparus
# en 6.0. dmTitle structuré et applicability étaient déjà dans 5.0.
_RULES_50 = [r for r in _RULES_60 if r.code not in {"PROC_STEP_VERB", "S1000D_DMC_FORMAT"}]


CATALOG: dict[str, list[StandardRule]] = {
    "5.0": _RULES_50,
    "6.0": _RULES_60,
}
