"""Portail qualité : couverture texte -> état de revuabilité."""

from __future__ import annotations

import fitz

from app.core import quality_gate


def _pdf_with_text() -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 100), "Remove the panel and inspect the bracket.", fontname="helv", fontsize=12)
    return doc


def _pdf_no_text() -> fitz.Document:
    doc = fitz.open()
    doc.new_page(width=400, height=300)  # page vide, aucune couche texte
    return doc


def test_assess_text_pdf_is_analyzable() -> None:
    doc = _pdf_with_text()
    try:
        report = quality_gate.assess(doc)
    finally:
        doc.close()
    assert report.state == quality_gate.STATE_ANALYZABLE
    assert report.coverage == 100
    assert report.pages_with_text == 1


def test_assess_scanned_pdf_is_unusable() -> None:
    doc = _pdf_no_text()
    try:
        report = quality_gate.assess(doc)
    finally:
        doc.close()
    assert report.state == quality_gate.STATE_UNUSABLE
    assert report.coverage == 0


def test_assess_partial_is_degraded() -> None:
    doc = fitz.open()
    p = doc.new_page(width=400, height=300)
    p.insert_text((50, 100), "Only this page has text.", fontname="helv", fontsize=12)
    doc.new_page(width=400, height=300)  # 2 pages sans texte
    doc.new_page(width=400, height=300)
    try:
        report = quality_gate.assess(doc)
    finally:
        doc.close()
    assert report.state == quality_gate.STATE_DEGRADED
    assert report.coverage == 33  # 1/3
