"""Unit tests for the new structural rule kinds."""

from __future__ import annotations

from app.checks import structural_checks
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def _parsed(text: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, spans=[])
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


def test_field_required_flags_missing_label() -> None:
    rule = {
        "code": "X1",
        "title": "Périodicité",
        "kind": "field_required",
        "severity": "error",
        "pattern": "Périodicité|Periodicity",
        "message": "manquant",
    }
    parsed = _parsed("Procédure A — Durée : 30 min, Personnel : 1.")
    out = structural_checks.run(parsed, [rule])
    assert len(out) == 1
    assert out[0].rule_code == "X1"


def test_field_required_silent_when_present() -> None:
    rule = {
        "code": "X1",
        "title": "Périodicité",
        "kind": "field_required",
        "severity": "error",
        "pattern": "Périodicité|Periodicity",
        "message": "manquant",
    }
    parsed = _parsed("Périodicité : 100 FH.")
    assert structural_checks.run(parsed, [rule]) == []


def test_step_pattern_ignores_bulleted_list() -> None:
    """`PROC_STEP_VERB` must NOT flag bulleted / dashed list items —
    those are typically field labels, not procedure steps. Real steps
    have an ordinal marker (1., 2), (3), Step 1.)."""
    rule = {
        "code": "VERB",
        "title": "Verb",
        "kind": "step_pattern",
        "severity": "warning",
        "pattern": r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b|[A-Z][a-z]{3,}(?:\s|$))",
        "message": "verbe requis",
    }
    text = (
        "Bullet list (not steps):\n"
        "• Applicabilité\n"
        "- Référence\n"
        "* Effectivité\n"
        "Numbered steps:\n"
        "1. Le panneau est retiré.\n"
        "2. Retirer la vis.\n"
    )
    out = structural_checks.run(_parsed(text), [rule])
    flagged = [s.original for s in out]
    # Bullets ARE NOT flagged
    assert not any("Applicabilité" in c for c in flagged)
    assert not any("Référence" in c for c in flagged)
    # Numbered step that doesn't start with a verb IS flagged
    assert any("Le panneau" in c for c in flagged)


def test_emit_returns_empty_proposed_for_detection_only() -> None:
    """Structural rules emit `proposed=""` so the UI knows it's a
    detection-only suggestion (no auto-correctable replacement)."""
    rule = {
        "code": "FIELD",
        "title": "Périodicité",
        "kind": "field_required",
        "severity": "error",
        "pattern": "Périodicité",
        "message": "manquant",
    }
    parsed = _parsed("Document without the required field.")
    out = structural_checks.run(parsed, [rule])
    assert len(out) == 1
    assert out[0].proposed == ""
    assert out[0].original  # original is the searched label


def test_step_pattern_skips_short_label_in_numbered_list() -> None:
    """Skip step bodies that look like a field label even when they sit
    in a numbered list — those are picked up by section_required."""
    rule = {
        "code": "VERB",
        "title": "Verb",
        "kind": "step_pattern",
        "severity": "warning",
        "pattern": r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir))",
        "message": "verbe requis",
    }
    text = "1. Applicabilité\n2. Retirer la vis du couvercle moteur principal.\n"
    out = structural_checks.run(_parsed(text), [rule])
    flagged = [s.original for s in out]
    assert not any("Applicabilité" in c for c in flagged)


def test_step_pattern_flags_nominal_step() -> None:
    rule = {
        "code": "VERB",
        "title": "Étape : verbe à l'infinitif",
        "kind": "step_pattern",
        "severity": "warning",
        "pattern": r"^(?:[A-ZÀ-Ÿ][a-zà-ÿ]+(?:er|ir|re|oir)\b|[A-Z][a-z]{3,}(?:\s|$))",
        "message": "verbe requis",
    }
    text = "1. Le panneau est retiré.\n2. Retirer la vis.\n3. Vérifier la position.\n"
    out = structural_checks.run(_parsed(text), [rule])
    codes = [s.original for s in out]
    assert any("Le panneau" in c for c in codes)
    assert not any("Retirer" in c for c in codes)
    assert not any("Vérifier" in c for c in codes)


def test_enum_value_flags_out_of_enum() -> None:
    rule = {
        "code": "ENUM",
        "title": "Niveau",
        "kind": "enum_value",
        "severity": "error",
        "pattern": "Line,Base,Shop",
        "message": "valeur hors énumération",
        "metadata": {"field_label": "Maintenance level"},
    }
    parsed = _parsed("Maintenance level: Garage")
    out = structural_checks.run(parsed, [rule])
    assert len(out) == 1


def test_field_consistency_flags_missing_spare() -> None:
    rule = {
        "code": "CONS",
        "title": "Rechange cohérente",
        "kind": "field_consistency",
        "severity": "error",
        "pattern": "task=replace|remplacer;spare=engine|moteur",
        "message": "rechange incohérente",
    }
    text_bad = "Procédure : Remplacer le calculateur. Rechange : N/A."
    text_ok = "Procédure : Remplacer le moteur. Rechange : moteur P/N 123."
    text_na = "Procédure : Inspecter visuellement le panneau."
    assert structural_checks.run(_parsed(text_bad), [rule])
    assert structural_checks.run(_parsed(text_ok), [rule]) == []
    assert structural_checks.run(_parsed(text_na), [rule]) == []
