"""Build an editorial revision plan from the saved preparation, without changing it."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.checks.client_registry import LoadedClientConfiguration
from app.checks.thales_rules.ata100 import revision_engine as revision
from app.core.compiled_rule_suggestions import resolve_display_template
from app.core.compiled_rules import CompiledRule
from app.core.pdf_annotate import MissingPageRepair, PreparationRepairRule, RevisionPlanSection
from app.core.preparation_check_service import PreparationDocument, preparation_metadata
from app.core.preparation_classification import page_requirements, preparation_rules
from app.core.preparation_state import get_record, load_preparation_mapping, state_payload
from app.db.models import Document

_LEP_RULE = "CUSTOM_PREP_LEP_MODIFIED_PAGES"
_ROR_RULE = "CUSTOM_PREP_ROR_NEW_ROW"


@dataclass(frozen=True)
class PreparationExport:
    missing_pages: tuple[MissingPageRepair, ...] = ()
    revision_sections: tuple[RevisionPlanSection, ...] = ()


def build_preparation_export(
    document: Document,
    db: Session,
    configuration: LoadedClientConfiguration,
) -> PreparationExport:
    if document.working_format != "pdf":
        return PreparationExport()
    record = get_record(db, document.id)
    if record is None:
        return PreparationExport()
    if record.source_version != document.current_version:
        return PreparationExport(revision_sections=(RevisionPlanSection(
            title="Préparation à actualiser",
            lines=(
                "La version du PDF a changé. Relancer la préparation avant de suivre un plan de révision.",
            ),
        ),))
    payload = state_payload(db, document, configuration.bundle.client_code)
    decisions = [dict(item) for item in payload["page_decisions"]]
    if not decisions:
        return PreparationExport(revision_sections=(RevisionPlanSection(
            title="Préparation incomplète",
            lines=(
                "Aucune décision de préparation disponible. Relancer la détection et confirmer les pages.",
            ),
        ),))
    reference_counts = Counter(
        _reference_key(item) for item in decisions if item.get("document_page")
    )
    for item in decisions:
        if item.get("classification_status") == "conflict" or reference_counts[_reference_key(item)] > 1:
            item["reference_warning"] = (
                f"Référence documentaire ambiguë ou classification conflictuelle : "
                f"{item.get('document_page') or 'non identifiée'}. Confirmer avant mise à jour de la LEP."
            )
            item["document_page"] = None
    metadata = preparation_metadata(configuration.mapping.fields, load_preparation_mapping(record))
    prepared_document = PreparationDocument(document, metadata)
    rules = preparation_rules(db, configuration.bundle)
    rules_by_id = {rule.id: rule for rule in rules}
    descriptions = {
        definition.code: definition.description
        for definition in configuration.bundle.rules
        if definition.preparation
    }
    requirements = page_requirements(db, configuration.bundle, record, decisions)
    missing_pages = tuple(
        MissingPageRepair(
            page_types=tuple(group),
            rules=tuple(
                PreparationRepairRule(
                    title=f"{rule.id} - {rule.topic}",
                    instructions=_rule_instructions(
                        rule, prepared_document, descriptions.get(rule.id),
                    ),
                )
                for rule in rules
                if list(group) in _target_groups(rule)
            ),
        )
        for group in requirements["absent_page_types"]
    )
    selected = [item for item in decisions if item.get("is_modified") is True]
    revision_date = revision.parse_date(str(metadata.get("meta_revision_date") or ""))
    if revision_date and revision_date.day is not None:
        try:
            date(revision_date.year, revision_date.month, revision_date.day)
        except ValueError:
            revision_date = None
    date_text = revision_date.text if revision_date and revision_date.day is not None else None
    number = str(metadata.get("meta_revision_number") or "").strip()
    sections = [RevisionPlanSection(
        title="Révision à préparer",
        lines=(
            f"Date de révision : {date_text or 'À RENSEIGNER dans le mapping de préparation (MMM JJ/AA)'}",
            f"Numéro de révision : {number or 'À RENSEIGNER dans le mapping de préparation'}",
            "Ce plan décrit les actions à réaliser dans le document source ; il ne les applique pas.",
            "Les numéros PDF désignent le document importé, pas les pages de cette annexe.",
            "Les pages non retenues ne doivent pas être redatées ni étoilées automatiquement.",
        ),
    )]
    page_lines: list[str] = []
    for decision in selected:
        page_lines.append(_page_label(decision))
        reasons = [*decision.get("failures", []), *decision.get("review_reasons", [])]
        for reason in reasons:
            rule = rules_by_id.get(reason["rule_id"])
            title = str(reason.get("title") or reason["rule_id"])
            page_lines.append(f"  - {title}")
            if rule is not None:
                page_lines.extend(
                    f"    {text}"
                    for text in _rule_instructions(rule, prepared_document, descriptions.get(rule.id))
                )
            elif reason.get("message"):
                page_lines.append(f"    {reason['message']}")
        if not reasons:
            page_lines.append("  - Page retenue manuellement : préciser les corrections métier.")
        page_lines.append(
            f"  - Après modification, date de révision du pied de page : {date_text}."
            if date_text else "  - Date du pied de page à confirmer : mapping de préparation incomplet."
        )
    sections.append(RevisionPlanSection(
        title=f"Pages à modifier ({len(selected)})",
        lines=tuple(page_lines) or ("Aucune page existante retenue pour modification.",),
    ))
    if _LEP_RULE in rules_by_id and (selected or missing_pages):
        sections.append(_lep_section(decisions, selected, missing_pages, date_text))
    if _ROR_RULE in rules_by_id and (selected or missing_pages):
        ror_pages = [item for item in decisions if item.get("page_type") == "ROR"]
        already_correct = any(
            result.get("rule_id") == _ROR_RULE and result.get("status") == "PASS"
            for item in ror_pages for result in item.get("rule_results", [])
        )
        ror_lines = [_page_label(item) for item in ror_pages] or ["Page ROR absente ou non identifiée."]
        if already_correct:
            ror_lines.append(
                "La ligne de révision a été vérifiée conforme lors de la détection : ne pas la dupliquer."
            )
        elif date_text and revision_date:
            insertion = revision._expected_ror_insertion_date(revision_date)
            ror_lines.extend((
                f"Ajouter ou compléter la ligne : REV. No. {number or 'À RENSEIGNER'} / "
                f"REVISION DATE {date_text} / INSERTION DATE {insertion.text}.",
                "Après modification du ROR, reporter aussi sa référence et la nouvelle date avec * "
                "dans la LEP.",
            ))
        else:
            ror_lines.append(
                "Ligne ROR à compléter : date de révision manquante ou sans jour ; aucun mois inventé."
            )
        sections.append(RevisionPlanSection(title="Record of Revisions (ROR)", lines=tuple(ror_lines)))
    highlights_rules = {
        "CUSTOM_PREP_HIGHLIGHTS_REVISION_DATE",
        "CUSTOM_PREP_HIGHLIGHTS_REVISION_NUMBER",
        "CUSTOM_PREP_HIGHLIGHTS_FOOTER_DATE",
    }
    if highlights_rules.intersection(rules_by_id) and (selected or missing_pages):
        highlights = [
            item for item in decisions
            if str(item.get("page_type") or "").startswith("HIGHLIGHTS")
        ]
        lines = [_page_label(item) for item in highlights] or ["Highlights absents ou non identifiés."]
        if "CUSTOM_PREP_HIGHLIGHTS_REVISION_DATE" in rules_by_id:
            lines.append(f"Date au-dessus du tableau : DATED {date_text or 'À RENSEIGNER'}.")
        if "CUSTOM_PREP_HIGHLIGHTS_REVISION_NUMBER" in rules_by_id:
            lines.append(
                f"Numéro au-dessus du tableau : REVISION No. {number or 'À RENSEIGNER'}."
            )
        if "CUSTOM_PREP_HIGHLIGHTS_FOOTER_DATE" in rules_by_id:
            lines.append(f"Date du pied de page Highlights : {date_text or 'À RENSEIGNER'}.")
        lines.append(
            "Vérifier les références et descriptions des changements du tableau Highlights avec la liste "
            "des pages à modifier. Confirmer le statut réel de chaque changement ; "
            "aucun statut n'est déduit ici."
        )
        sections.append(RevisionPlanSection(
            title="Highlights : cohérence de la révision", lines=tuple(lines),
        ))
    warnings = _unresolved_lines(decisions, requirements["missing_page_types"], missing_pages)
    if warnings:
        sections.append(RevisionPlanSection(
            title="Points à confirmer avant finalisation", lines=tuple(warnings),
        ))
    return PreparationExport(missing_pages=missing_pages, revision_sections=tuple(sections))


def _target_groups(rule: CompiledRule) -> list[list[str]]:
    return (
        ([[rule.target.page_type]] if rule.target.page_type else [])
        + ([rule.target.page_types] if rule.target.page_types else [])
    )


def _page_label(decision: Mapping[str, Any]) -> str:
    reference = decision.get("document_page")
    return (
        f"Page PDF {decision['page']} | {decision.get('page_type') or 'type à confirmer'} | "
        f"Référence documentaire : {reference or 'NON IDENTIFIÉE - à confirmer'}"
    )


def _reference_key(decision: Mapping[str, Any]) -> str:
    reference = str(decision.get("document_page") or "").strip()
    return revision.normalize_page_key(reference) or reference.casefold()


def _rule_instructions(
    rule: CompiledRule,
    document: PreparationDocument,
    description: str | None,
) -> tuple[str, ...]:
    instructions = list(dict.fromkeys(
        value.strip()
        for value in (
            description, rule.source_instruction, rule.manual_instruction, rule.semantic_instruction,
        )
        if value and value.strip()
    ))
    expected = [check.expected_display for check in rule.checks if check.expected_display]
    instructions.extend(f"Valeur attendue : {value}" for value in expected)
    if not instructions:
        instructions.append(rule.failure_message or rule.topic)
        for check in rule.checks:
            if check.expected is not None:
                instructions.append(f"Critère {check.field} ({check.operator}) : {check.expected}")
    return tuple(resolve_display_template(text, document) for text in instructions)


def _lep_section(
    decisions: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    missing_pages: tuple[MissingPageRepair, ...],
    date_text: str | None,
) -> RevisionPlanSection:
    lep_pages = [item for item in decisions if item.get("page_type") == "LEP"]
    lines = [_page_label(item) for item in lep_pages] or [
        "LEP absente ou non identifiée : la créer ou la localiser."
    ]
    lines.append("Entrées à mettre à jour dans la liste des pages effectives (LEP) :")
    for item in selected:
        reference = item.get("document_page")
        if not reference:
            lines.append(
                f"- Page PDF {item['page']} : référence documentaire à identifier "
                "avant mise à jour de la LEP."
            )
        elif date_text:
            lines.append(f"- {reference} | {date_text} * (page PDF {item['page']})")
        else:
            lines.append(
                f"- {reference} : date à confirmer, puis ajouter l'astérisque * (page PDF {item['page']})."
            )
    for missing in missing_pages:
        lines.append(
            f"- Page(s) à créer : {' / '.join(missing.page_types)}. Attribuer une référence documentaire, "
            f"puis ajouter une entrée avec {date_text + ' *' if date_text else 'la nouvelle date et *'}."
        )
    lines.extend((
        "L'astérisque * appartient à l'entrée LEP ; il ne remplace pas la date du pied de page.",
        "Si la mise à jour modifie une page LEP, ROR ou Highlights non retenue au départ, "
        "la compter aussi parmi les pages révisées : pied de page et entrée LEP à mettre à jour.",
        "Ne pas utiliser le numéro PDF comme référence documentaire sans vérification.",
    ))
    return RevisionPlanSection(title="LEP : nouvelle date et astérisque *", lines=tuple(lines))


def _unresolved_lines(
    decisions: list[dict[str, Any]],
    missing_groups: list[list[str]],
    missing_pages: tuple[MissingPageRepair, ...],
) -> list[str]:
    lines = [
        f"{_page_label(item)} : décision de modification non confirmée."
        for item in decisions if item.get("is_modified") is None
    ]
    lines.extend(
        f"{_page_label(item)} : déclarée inchangée malgré des contrôles en échec ; arbitrage nécessaire."
        for item in decisions if item.get("is_modified") is False and item.get("failures")
    )
    lines.extend(
        f"Page PDF {item['page']} : {item['reference_warning']}"
        for item in decisions if item.get("reference_warning")
    )
    lines.extend(
        f"Type {' / '.join(group)} non localisé : confirmer la page ou son absence."
        for group in missing_groups
    )
    if missing_pages:
        lines.append(
            "Les pages absentes sont détaillées dans l'annexe suivante. Leur pagination et leurs impacts "
            "LEP, Highlights et table des matières restent à confirmer après création."
        )
    return lines
