"""Tests unitaires - detection en-tete + mapping colonnes CATI."""

from __future__ import annotations

from app.core.column_map import detect_header, match_field, norm, role_of


def test_norm_strips_accents_and_case() -> None:
    assert norm("Référence") == "reference"
    assert norm("  FIG   REP ") == "fig rep"


def test_match_field_keywords() -> None:
    assert match_field("FIG REP") == "fig"
    assert match_field("Designation") == "designation"
    assert match_field("Reference") == "reference"
    assert match_field("QUANTITE") == "qty"
    assert match_field("Symbole") == "symbole"
    assert match_field("") is None


def test_role_of() -> None:
    assert role_of("Client") == "ref_client"
    assert role_of("Interne") == "ref_interne"
    assert role_of("Fournisseur") == "ref_fournisseur"
    assert role_of("3A") is None


def test_detect_header_multiline_cati() -> None:
    grid = [
        ["TEST BOM", "", "", "", "", "", "", ""],
        ["FIG REP", "DESIGNATION", "SYMBOLE", "IDENTIFICATION", "", "QUANTITE", "", "APP"],
        ["", "", "", "Code", "Reference", "ES", "EM", ""],
        ["1", "2", "7", "3A", "3B", "5A", "5B", "6"],
    ]
    header_idx, colmap = detect_header(grid)
    assert header_idx == 1
    assert colmap["fig"] == 0
    assert colmap["designation"] == 1
    assert colmap["code"] == 3
    assert colmap["reference"] == 4
    assert colmap["qty"] == 5
