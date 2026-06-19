"""Catalogue ATA 100 (rev 38) - chapitrage standard, porte du pdf-reviewer.

Ne contient QUE des regles ATA 100 generiques (format de chapitrage, references
croisees, donnees techniques). Les controles propres a un client / a une revue
CMM (raisons sociales, footer normalise, Highlights, Fiche suiveuse, barre de
revision...) ne sont PAS en dur ici : ils proviennent de la **checklist
importee** par l'utilisateur (table `Rule`). Avant tout import, seul l'ATA 100
de base s'applique.
"""

from __future__ import annotations

from app.checks.standards._base import StandardRule


_RULES_REV38 = [
    StandardRule(
        code="ATA_CHAPTER_REF",
        title="Reference chapitre ATA : separateurs",
        description=(
            "Les renvois doivent suivre le format chapitre-section-sujet avec des "
            "tirets (ex : 24-21-00). Corrige les separateurs incorrects "
            "(point, espace, slash) ; ne signale pas les references deja bien formees."
        ),
        kind="regex_replace",
        severity="warning",
        pattern=r"\b(\d{2})[ ._/](\d{2})[ ._/](\d{2})\b",
        replacement=r"\1-\2-\3",
        message="Reference ATA : utiliser des tirets (CH-SE-SU).",
        example_invalid="34.10.42",
        example_valid="34-10-42",
    ),
    StandardRule(
        code="ATA_CHAPTER_RANGE",
        title="Chapitre ATA dans l'intervalle 00-99",
        description="Le chapitre principal ATA 100 est numerote de 00 a 99.",
        kind="regex_flag",
        severity="error",
        pattern=r"\bCh(?:apter|apitre)\s+(?:[1-9]\d{2,}|0?[a-zA-Z])",
        message="Chapitre ATA hors plage 00-99.",
    ),
    StandardRule(
        code="ATA_NO_AMBIGUOUS_QUANT",
        title="Quantificateurs ambigus a eviter",
        description="Eviter « some », « a few », « several » - preferer une quantite chiffree.",
        kind="regex_flag",
        severity="info",
        pattern=r"\b(?:some|a few|several|plusieurs)\b",
        message="Quantificateur ambigu - preferer une valeur chiffree.",
    ),
    StandardRule(
        code="ATA_TORQUE_DUAL_UNIT",
        title="Couple en unite duale (N.m + lb.ft)",
        description=(
            "Les valeurs de couple doivent etre presentees dans les deux unites "
            "(SI primaire, imperial secondaire)."
        ),
        kind="regex_flag",
        severity="info",
        pattern=r"\b\d+(?:\.\d+)?\s*(?:N[.]?m|lb[.]?ft)\b",
        message="Couple - verifier la presence des deux unites (N.m / lb.ft).",
    ),
]


CATALOG: dict[str, list[StandardRule]] = {
    "rev 38": _RULES_REV38,
}
