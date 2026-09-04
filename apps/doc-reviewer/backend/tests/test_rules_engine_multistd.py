"""End-to-end check that the engine only runs rules from the active standard."""

from __future__ import annotations

import json
from typing import Any

from app.core.rules_engine import run_all
from app.db.models import StandardVersion
from app.db.session import SessionLocal
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def _parsed(text: str) -> ParsedPdf:
    page = ParsedPage(page=1, text=text, spans=[])
    return ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)


class _DocStub:
    target_unit_system = "auto"


def _doc() -> _DocStub:
    return _DocStub()


def _get_version(session, code: str) -> StandardVersion:
    from sqlalchemy import select

    from app.db.models import Standard

    std = session.scalar(select(Standard).where(Standard.code == code))
    assert std is not None
    return std.versions[0]


def test_mat10000_run_does_not_emit_ata_codes() -> None:
    session = SessionLocal()
    try:
        mat_v = _get_version(session, "MAT10000")
        # Sample text triggers fields/sections from both norms.
        parsed = _parsed(
            "Procedure: Replace the engine.\n"
            "Périodicité: 200 FH.\n"
            "1. Le panneau est retiré.\n"
        )
        out = run_all(parsed, _doc(), session, [mat_v])
        codes = {s.rule_code for s in out}
        assert not any(c.startswith("ATA22_") for c in codes)
        assert not any(c.startswith("ATA_") for c in codes)
    finally:
        session.close()


def test_no_standard_version_only_runs_transverse() -> None:
    session = SessionLocal()
    try:
        parsed = _parsed("A simple line with no fields.")
        out = run_all(parsed, _doc(), session, None)
        # No catalog → no built-in rule code emitted. Custom transverse
        # rules from the demo seed may still flag entries, so we just
        # verify no standard catalog code appears.
        codes = {s.rule_code for s in out}
        assert not any(
            c.startswith(("MAT_", "S2K_", "ATA_", "ATA22_", "STE_", "S1000D_", "PROC_"))
            for c in codes
        )
    finally:
        session.close()


def test_catalog_json_is_well_formed_for_every_builtin() -> None:
    session = SessionLocal()
    try:
        for sv in session.query(StandardVersion).filter(StandardVersion.builtin.is_(True)):
            data: Any = json.loads(sv.catalog_json or "[]")
            assert isinstance(data, list)
            assert all(isinstance(r, dict) and "code" in r and "kind" in r for r in data)
    finally:
        session.close()
