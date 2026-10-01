"""Controles geometriques (layout) : titre non centre, pied absent, bbox en points."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz

from app.checks import layout_checks


def _pdf_no_footer_with_indent() -> str:
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((40, 60), "GENERAL DESCRIPTION", fontsize=22)
    # Corps aligne a gauche (x=40) + une ligne nettement indentee a droite.
    for i in range(7):
        page.insert_text((40, 120 + i * 20), f"Body line number {i} of the procedure.", fontsize=10)
    page.insert_text((160, 260), "Indented outlier line.", fontsize=10)
    # Pas de texte en bas de page -> pied absent.
    path = Path(tempfile.mkdtemp(prefix="dr_layout_")) / "doc.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_layout_emits_findings_with_points_bbox() -> None:
    findings = layout_checks.run(_pdf_no_footer_with_indent())
    codes = {f.rule_code for f in findings}
    # Pied de page absent attendu ; plus de regle « titre non centre ».
    assert "LAYOUT_FOOTER" in codes
    assert "LAYOUT_TITLE_CENTER" not in codes
    assert all(f.rule_kind == "layout" and f.proposed == "" for f in findings)
    # Les findings localises portent une bbox en points (4 floats).
    located = [f for f in findings if f.bbox is not None]
    assert all(len(f.bbox) == 4 for f in located)


def test_layout_run_missing_file_returns_empty() -> None:
    assert layout_checks.run(None) == []
    assert layout_checks.run("does_not_exist.pdf") == []


def test_layout_findings_limit_marks_remaining_pages_incomplete(tmp_path, monkeypatch) -> None:
    doc = fitz.open()
    for page_index in range(2):
        page = doc.new_page(width=600, height=800)
        page.insert_text((40, 120), f"Synthetic page {page_index + 1}", fontsize=10)
    path = tmp_path / "synthetic-layout.pdf"
    doc.save(str(path))
    doc.close()
    monkeypatch.setattr(layout_checks, "_MAX_FINDINGS", 1)
    warnings: list[str] = []

    findings = layout_checks.run(str(path), warnings=warnings)

    assert len(findings) == 1
    assert len(warnings) == 1
    assert "pages restantes n'ont pas été vérifiées" in warnings[0]
