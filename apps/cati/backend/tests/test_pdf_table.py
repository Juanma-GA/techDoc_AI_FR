"""Tests - regroupement des sous-lignes CATI (fonction pure group_grid)."""

from __future__ import annotations

from app.parsers.pdf_table import _figreflink, _split_aplomb, group_grid


def _cati_grid() -> list[list]:
    return [
        ["TEST BOM ANONYMISE", "", "", "", "", "", "", ""],
        ["FIG REP", "DESIGNATION", "SYMBOLE", "IDENTIFICATION", "", "QUANTITE", "", "APP"],
        ["", "", "", "Code", "Reference", "ES", "EM", ""],
        ["1", "2", "7", "3A", "3B", "5A", "5B", "6"],  # ligne des numeros de colonne
        ["10A", ".Bati equipe + visserie", "", "Client", "C1023", "1", "", ""],
        ["", "", "", "Interne", "I1023", "", "", ""],
        ["", "", "", "Fournisseur", "F1023", "", "", ""],
        ["20A", ".Isolateur + ecrou", "", "Client", "C2045", "3", "", ""],
        ["", "", "", "Interne", "I2045", "", "", ""],
        ["", "", "", "Fournisseur", "F2045", "", "", ""],
    ]


def test_split_aplomb() -> None:
    assert _split_aplomb(".Bati equipe") == (".", "Bati equipe")
    assert _split_aplomb("..Sous niveau") == ("..", "Sous niveau")
    assert _split_aplomb("Sans point") == ("", "Sans point")


def test_figreflink() -> None:
    assert _figreflink("10A") == 10
    assert _figreflink("120A") == 120
    assert _figreflink("") is None


def test_group_grid_regroups_subrows_and_skips_legend() -> None:
    items = group_grid(_cati_grid(), page=3)
    # 2 articles seulement : la ligne des numeros de colonne est ecartee.
    assert len(items) == 2

    first = items[0]
    assert first["fig"] == "10A"
    assert first["figreflink"] == 10
    assert first["aplomb"] == "."
    assert first["description"] == "Bati equipe + visserie"
    assert first["qty"] == "1"
    assert first["ref_client"] == "C1023"
    assert first["ref_interne"] == "I1023"
    assert first["ref_fournisseur"] == "F1023"
    assert first["source_page"] == 3

    assert items[1]["fig"] == "20A"
    assert items[1]["ref_fournisseur"] == "F2045"


def test_group_grid_empty_on_non_bom() -> None:
    assert group_grid([["a", "b"], ["c", "d"]]) == []
    assert group_grid([]) == []
