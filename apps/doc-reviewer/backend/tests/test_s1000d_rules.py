"""THALES S1000D norm: catalog contract and rule behaviour on synthetic PDF text."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.checks.client_registry import load_active_client_configuration
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfLink, PdfVectorPrimitive, Span

_BUNDLE = load_active_client_configuration().bundle
_DEFINITIONS = {
    definition.code: definition
    for definition in _BUNDLE.rules
    if definition.bundle_code == "s1000d"
}

_REVISION_META = {
    "meta_revision_date": "OCT 30/26",
    "meta_revision_number": "05",
    "meta_first_issue_date": "JUL 2000",
    "meta_manufacturer": "Airbus",
}


def _loedm(*, dm2_status: str = "C", ipl_status: str = "") -> str:
    return (
        "LIST OF EFFECTIVE DATA MODULES\n"
        "F9111CMON-A-20-02-00-00A-800A-A\n001-00\n2026-10-30\nStorage - General procedure\nC\n"
        f"F9111CMON-A-72-00-00-00A-500A-A\n001-00\n2026-10-30\nDisassembly\n{dm2_status}\n"
        f"F9111CMON-A-72-00-00-00A-941A-A\n001-00\n2025-05-12\nIllustrated parts data\n{ipl_status}\n"
    )


_LOEDM = _loedm()


def _pdf(*texts: str, pages: list[ParsedPage] | None = None) -> ParsedPdf:
    built = pages or [ParsedPage(page=index, text=text) for index, text in enumerate(texts, start=1)]
    return ParsedPdf(
        page_count=len(built),
        pages=built,
        full_text="\n".join(page.text for page in built),
        is_signed=False,
    )


def _run(code: str, pdf: ParsedPdf, **meta: Any) -> tuple[str, list[Any]]:
    document = SimpleNamespace(client_metadata={}, **meta)
    results, suggestions = execute_pdf_rules(
        pdf,
        [_DEFINITIONS[code].compiled_rule],
        document=document,
        client_operations=_BUNDLE.operations,
        client_entities=_BUNDLE.mapping.entities,
    )
    assert len(results) == 1
    return results[0].status, suggestions


def _bar_page(number: int, text: str, *, bar: bool) -> ParsedPage:
    primitives = (
        [
            PdfVectorPrimitive(
                kind="line", bbox=(30.0, 100.0, 30.0, 200.0), color=(0.0, 0.0, 0.0), fill=None, width=2.0
            )
        ]
        if bar
        else [
            PdfVectorPrimitive(
                kind="line", bbox=(300.0, 600.0, 400.0, 600.0), color=(0.0, 0.0, 0.0), fill=None, width=1.0
            )
        ]
    )
    return ParsedPage(
        page=number,
        text=text,
        spans=[Span(text="Body", bbox=(70.0, 100.0, 200.0, 112.0), page=number, font="Arial", size=10.0)],
        page_width=600.0,
        page_height=800.0,
        vector_primitives=primitives,
    )


def test_catalog_contains_the_32_automatable_excel_rules_with_translations() -> None:
    assert len(_DEFINITIONS) == 32
    for definition in _DEFINITIONS.values():
        assert definition.code.startswith("S1000D_")
        assert definition.compiled_rule.origin_ref == f"THALES-S1000D:v1:{definition.code}"
        assert definition.description and definition.message
        assert {"description", "message"} <= set(definition.translations["en"])
        assert not definition.preparation
    assert {definition.bundle_label for definition in _DEFINITIONS.values()} == {"S1000D"}


def test_s1000d_catalog_starts_disabled_while_ata100_stays_enabled() -> None:
    specs = _BUNDLE.standard_specs
    assert set(specs["THALES-S1000D"]["default_disabled_rule_codes_by_version"]["v1"]) == set(
        _DEFINITIONS
    )
    assert "default_disabled_rule_codes_by_version" not in specs["THALES-CUSTOM"]
    assert {rule.bundle_code for rule in _BUNDLE.rules} == {"ata100", "s1000d", "ste100_rules"}


def test_unknown_control_is_rejected() -> None:
    operation = _BUNDLE.operations["s1000d_content"]
    runtime = SimpleNamespace(parsed_pdf=_pdf("x"), is_docx=False, document=None)
    with pytest.raises(ValueError, match="known control"):
        operation.execute(SimpleNamespace(runtime=runtime, targets=()), {"control": "nope"})


# ---------------------------------------------------------------- text rules


@pytest.mark.parametrize(
    ("code", "good", "bad"),
    [
        (
            "S1000D_QA_FIRST_VERIFICATION",
            "Quality assurance\nFirst verification: TABTOP",
            "Quality assurance\nFirst verification: Unclassified",
        ),
        (
            "S1000D_THALES_ADDRESS",
            "75-77 AV MARCEL DASSAULT\n33700 MERIGNAC\nFRANCE\nTel: 05 24 44 77 40\nwww.thalesgroup.com",
            "75-77 AV MARCEL DASSAULT\n33700 MERIGNAC\nFRANCE\nwww.thalesgroup.com",
        ),
        (
            "S1000D_SPM_LINK_AIRBUS",
            "Refer to SPM 20-02-00 - STANDARD PRACTICES MANUAL (SPM) for details.",
            "Refer to SPM 20-02-00 for details.",
        ),
        (
            "S1000D_SOPM_LINK_BOEING",
            "Refer to SOPM 20-02-00 - STANDARD OVERHAUL PRACTICES MANUAL (SOPM).",
            "Refer to SOPM 20-02-00 - STANDARD PRACTICES MANUAL (SPM).",
        ),
        (
            "S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF",
            "Torque wrench\nNot specific-12345\nLOCAL\n1",
            "Torque wrench\nNot specific-12345\n1\nSpecial tool\nQty",
        ),
        (
            "S1000D_TOOL_NAME_NO_SPACE",
            "Not specific-12345 LOCAL",
            "Not  specific-12345 LOCAL",
        ),
        (
            "S1000D_SHOP_VERIFICATION",
            "Shop Verification:\nA. Verification of the procedures in this manual",
            "Testing and fault isolation only.",
        ),
        (
            "S1000D_HUMIDITY_DM_REFERENCE",
            "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00,\n"
            "F9111CMON-A-20-02-00-00A-800A-A \u2013 Storage - General procedure.",
            "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00.",
        ),
        (
            "S1000D_STORAGE_TEMPERATURE_NOTE",
            "NOTE\nDuring storage operations, make sure that the environmental conditions are as follows:\n"
            "- Temperature:Refer to SPM 20-02-00 - STANDARD PRACTICES MANUAL (SPM),\n"
            "Refer to F9111CMON-A-20-02-00-00A-812A-A - Storage and Transportation of Assemblies.",
            "NOTE\nDuring storage operations, make sure that the environmental conditions are as follows:\n"
            "- Temperature: -40 deg. C to +70 deg. C",
        ),
        (
            "S1000D_NO_SILICA_GEL_DESICCANT",
            "Store the unit in a sealed bag.",
            "Add a dessicant bag in the container.",
        ),
        (
            "S1000D_DATA_RESTRICTION_COPYRIGHT",
            "\u00a9 2000-2026 THALES AVS FRANCE SAS. This document and any data included are the "
            "property of THALES AVS FRANCE SAS. They cannot be reproduced, disclosed or used "
            "without the company's prior written approval",
            "\u00a9 2000-2026 THALES AVS FRANCE SAS. All rights reserved.",
        ),
    ],
)
def test_text_rules_pass_on_reference_text_and_fail_on_deviation(
    code: str, good: str, bad: str
) -> None:
    meta = {"meta_revision_date": "OCT 30/26", "meta_first_issue_date": "JUL 2000"}
    assert _run(code, _pdf(good), **meta)[0] == "PASS"
    status, suggestions = _run(code, _pdf(bad), **meta)
    assert status == "FAIL"
    assert suggestions


def test_spm_link_is_checked_independently_of_sopm_links() -> None:
    pdf = _pdf("Refer to SOPM 20-02-00 - STANDARD OVERHAUL PRACTICES MANUAL (SOPM).")
    assert _run("S1000D_SPM_LINK_AIRBUS", pdf)[0] == "PASS"
    assert _run("S1000D_SOPM_LINK_BOEING", pdf)[0] == "PASS"


def test_not_specific_tool_accepts_local_before_or_after() -> None:
    assert _run("S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF", _pdf("LOCAL Not specific-12345 1"))[0] == "PASS"
    assert _run("S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF", _pdf("Not specific-12345 LOCAL 1"))[0] == "PASS"
    assert _run("S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF", _pdf("Not specific-12345 FR123 1"))[0] == "FAIL"


# -------------------------------------------------------------- LOEDM controls


def test_loedm_dates_follow_the_revision_date() -> None:
    pdf = _pdf(_LOEDM)
    assert _run("S1000D_MCO_DM_DATES", pdf, **_REVISION_META)[0] == "PASS"
    status, suggestions = _run("S1000D_MIGRATION_DM_DATES", pdf, **_REVISION_META)
    assert status == "FAIL"
    assert [item.original for item in suggestions] == ["F9111CMON-A-72-00-00-00A-941A-A"]


def test_loedm_controls_are_inconclusive_without_loedm_or_revision_date() -> None:
    assert _run("S1000D_MIGRATION_DM_DATES", _pdf("No list here"), **_REVISION_META)[0] == "INCONCLUSIVE"
    assert _run("S1000D_MIGRATION_DM_DATES", _pdf(_LOEDM))[0] == "INCONCLUSIVE"


def test_loedm_status_controls() -> None:
    assert _run("S1000D_MCO_LOEDM_STATUS", _pdf(_LOEDM), **_REVISION_META)[0] == "PASS"
    missing = _loedm(dm2_status="")
    assert _run("S1000D_MCO_LOEDM_STATUS", _pdf(missing), **_REVISION_META)[0] == "FAIL"
    assert _run("S1000D_MIGRATION_LOEDM_STATUS", _pdf(_LOEDM))[0] == "FAIL"
    generic = _LOEDM.replace("Illustrated parts data", "Generic parts data")
    assert _run("S1000D_MIGRATION_LOEDM_STATUS", _pdf(generic))[0] == "PASS"


# ----------------------------------------------------------- revision bars


def _dm_pdf(*, changed_bar: bool, status_bar: bool, rfu: bool = True) -> ParsedPdf:
    changed = "F9111CMON-A-72-00-00-00A-500A-A\nDisassembly" + ("\nRFU: new torque" if rfu else "")
    return _pdf(
        pages=[
            ParsedPage(page=1, text=_loedm(ipl_status="R")),
            _bar_page(2, changed, bar=changed_bar),
            _bar_page(3, "F9111CMON-A-72-00-00-00A-941A-A\nIllustrated parts data", bar=status_bar),
        ]
    )


def test_changed_dm_needs_revision_bars_and_rfu() -> None:
    assert _run("S1000D_CHANGED_DM_REVISION_BARS", _dm_pdf(changed_bar=True, status_bar=False))[0] == "PASS"
    status, suggestions = _run(
        "S1000D_CHANGED_DM_REVISION_BARS", _dm_pdf(changed_bar=False, status_bar=False)
    )
    assert status == "FAIL"
    assert suggestions[0].page == 2
    status, _ = _run(
        "S1000D_CHANGED_DM_REVISION_BARS", _dm_pdf(changed_bar=True, status_bar=False, rfu=False)
    )
    assert status == "PASS"  # no RFU anywhere in the PDF: RFUs are not printed, nothing to compare


def test_revised_dm_must_not_carry_revision_bars() -> None:
    assert _run("S1000D_UNCHANGED_DM_NO_REVISION_BARS", _dm_pdf(changed_bar=True, status_bar=False))[0] == "PASS"
    status, suggestions = _run(
        "S1000D_UNCHANGED_DM_NO_REVISION_BARS", _dm_pdf(changed_bar=True, status_bar=True)
    )
    assert status == "FAIL"
    assert suggestions[0].page == 3
    assert suggestions[0].bbox[1:4:2] == (100.0, 200.0)


def test_revision_bars_are_inconclusive_when_the_pdf_has_no_vectors() -> None:
    assert _run("S1000D_CHANGED_DM_REVISION_BARS", _pdf(_LOEDM, "F9111CMON-A-72-00-00-00A-500A-A\nx"))[0] == (
        "INCONCLUSIVE"
    )


def test_ipl_rules_use_the_941_data_module_status() -> None:
    ipl_changed = _loedm(ipl_status="C")

    def ipl_pdf(*, bar: bool) -> ParsedPdf:
        return _pdf(
            pages=[
                ParsedPage(page=1, text=ipl_changed),
                _bar_page(2, "F9111CMON-A-72-00-00-00A-941A-A\nFigure 1 Parts\nITEM 1", bar=bar),
            ]
        )

    assert _run("S1000D_IPL_REVISION_BARS", ipl_pdf(bar=True))[0] == "PASS"
    assert _run("S1000D_IPL_REVISION_BARS", ipl_pdf(bar=False))[0] == "FAIL"
    assert _run("S1000D_IPL_ILLUSTRATION_REVISION_BAR", ipl_pdf(bar=True))[0] == "PASS"
    assert _run("S1000D_IPL_ILLUSTRATION_REVISION_BAR", ipl_pdf(bar=False))[0] == "INCONCLUSIVE"
    unchanged = _pdf(
        pages=[
            ParsedPage(page=1, text=_LOEDM),
            _bar_page(2, "F9111CMON-A-72-00-00-00A-941A-A\nFigure 1 Parts", bar=False),
        ]
    )
    assert _run("S1000D_IPL_REVISION_BARS", unchanged)[0] == "PASS"


# ----------------------------------------------------------------- links


def _link_page(number: int, text: str, link: PdfLink) -> ParsedPage:
    return ParsedPage(page=number, text=text, links=[link])


def test_ipl_and_procedure_links_must_have_a_destination() -> None:
    ok = PdfLink(bbox=(10.0, 10.0, 50.0, 20.0), kind="internal", target_page=1, text="Fig. 1")
    broken = PdfLink(bbox=(10.0, 30.0, 50.0, 40.0), kind="internal", target_page=None, text="Fig. 2")
    procedure = "F9111CMON-A-72-00-00-00A-500A-A\nMain procedure\nUse the tool"
    ipl = "ILLUSTRATED PARTS LIST\nITEM 1"

    good_pdf = _pdf(pages=[_link_page(1, procedure, ok), _link_page(2, ipl, ok)])
    bad_pdf = _pdf(pages=[_link_page(1, procedure, broken), _link_page(2, ipl, broken)])
    assert _run("S1000D_TOOL_LINK_WORKS", good_pdf)[0] == "PASS"
    assert _run("S1000D_IPL_LINKS", good_pdf)[0] == "PASS"
    status, suggestions = _run("S1000D_TOOL_LINK_WORKS", bad_pdf)
    assert status == "FAIL"
    assert [item.page for item in suggestions] == [1]
    status, suggestions = _run("S1000D_IPL_LINKS", bad_pdf)
    assert status == "FAIL"
    assert [item.page for item in suggestions] == [2]
    assert _run("S1000D_IPL_LINKS", _pdf(procedure, ipl))[0] == "INCONCLUSIVE"


# ------------------------------------------------------------ front matter


def test_revision_identification_on_the_title_page() -> None:
    good = _pdf("TITLE PAGE\nRevision No. 05\nIssue date: 2026-10-30", "RECORD OF REVISIONS\n")
    bad = _pdf("TITLE PAGE\nRevision No. 04\nIssue date: 2026-05-01", "RECORD OF REVISIONS\n")
    assert _run("S1000D_MIGRATION_REVISION_ISSUE", good, **_REVISION_META)[0] == "PASS"
    status, suggestions = _run("S1000D_MIGRATION_REVISION_ISSUE", bad, **_REVISION_META)
    assert status == "FAIL"
    assert len(suggestions) == 2
    assert _run("S1000D_MIGRATION_REVISION_ISSUE", _pdf("TITLE"), **_REVISION_META)[0] == "INCONCLUSIVE"


def test_revision_record_needs_a_row_for_the_current_revision() -> None:
    cover = "TITLE PAGE"
    good = _pdf(cover, "RECORD OF REVISIONS\nRev 04\n2025-05-01\nRev 05\n2026-10-30\nNew DMs")
    bad = _pdf(cover, "RECORD OF REVISIONS\nRev 04\n2025-05-01")
    assert _run("S1000D_MCO_REVISION_ROW", good, **_REVISION_META)[0] == "PASS"
    assert _run("S1000D_MCO_REVISION_ROW", bad, **_REVISION_META)[0] == "FAIL"
    assert _run("S1000D_MCO_REVISION_ROW", _pdf(cover), **_REVISION_META)[0] == "INCONCLUSIVE"


def test_copyright_years_follow_first_issue_and_revision_years() -> None:
    statement = (
        "\u00a9 {years} THALES AVS FRANCE SAS. This document and any data included are the "
        "property of THALES AVS FRANCE SAS. They cannot be reproduced, disclosed or used "
        "without the company's prior written approval"
    )
    assert _run("S1000D_DATA_RESTRICTION_COPYRIGHT", _pdf(statement.format(years="2000-2026")), **_REVISION_META)[0] == "PASS"
    status, suggestions = _run(
        "S1000D_DATA_RESTRICTION_COPYRIGHT", _pdf(statement.format(years="2000-2024")), **_REVISION_META
    )
    assert status == "FAIL"
    assert suggestions[0].proposed == "\u00a9 2000-2026"


_SB_TEMPLATE = (
    "1. Service bulletin record\n"
    "The Service Bulletin (SB) record lists all SBs incorporated in the manual.\n"
    "The SB record has the five columns that follow:\n"
    "- SB \u2013 Number and revision:\n"
    "This is the number of the SB and its revision number. If no SB has an effect on the manual content, "
    "the\ncomment \u201cNone\u201d is given.\n"
    "- SB \u2013 Title:\nThis is the subject of the SB.\n"
    "- Equipment part number modification state:\n"
    "This is the equipment part number modification state. Only the part number(s) or amendment\n"
    "introduced is (are) listed. If the SB data has no effect on the manual content,\n"
    "the comment \u201cNo effect\u201d is given.\n"
    "- Service bulletin release date:\nThis is the release date of the SB\n"
    "- Inserted number:\nThis is the version of the manual that the SB has been incorporated into.\n"
    "NOTE\nThe Service Information Letters (SILs) which have an effect on the manual content are\n"
    "given at the end of the table.\n"
    "Table 1 Service bulletin record\nSB\nNumber and\nrevision\nTitle\n"
    "Equipment part number\nmodification state\nSB release date\nInserted number\n"
)


def test_sb_record_must_follow_the_template() -> None:
    assert _run("S1000D_SB_RECORD_FORMAT", _pdf("cover", _SB_TEMPLATE))[0] == "PASS"
    outdated = _SB_TEMPLATE.replace("This is the subject of the SB.", "Subject.")
    status, suggestions = _run("S1000D_SB_RECORD_FORMAT", _pdf("cover", outdated))
    assert status == "FAIL"
    assert "This is the subject of the SB." in suggestions[0].message
    assert _run("S1000D_SB_RECORD_FORMAT", _pdf("cover"))[0] == "INCONCLUSIVE"


def test_abbreviations_must_define_sb_and_sil() -> None:
    good = "LIST OF ABBREVIATIONS\nSB Service Bulletin\nSIL Service Information Letter\n"
    bad = "LIST OF ABBREVIATIONS\nSB Service Bulletin\nATA Air Transport Association\n"
    assert _run("S1000D_SB_SIL_ACRONYMS", _pdf(good))[0] == "PASS"
    assert _run("S1000D_SB_SIL_ACRONYMS", _pdf(bad))[0] == "FAIL"
    assert _run("S1000D_SB_SIL_ACRONYMS", _pdf("nothing"))[0] == "INCONCLUSIVE"


# -------------------------------------------------------------- content rules


def test_numbers_zero_to_nine_in_words_and_ten_plus_in_digits() -> None:
    assert _run("S1000D_NUMBERS_IN_WORDS", _pdf("Install two screws and tighten to 5 N.m. Replace 12 seals."))[0] == "PASS"
    status, suggestions = _run("S1000D_NUMBERS_IN_WORDS", _pdf("Install 2 screws on the unit."))
    assert status == "FAIL"
    assert suggestions[0].proposed == "Install two screws"
    status, suggestions = _run("S1000D_NUMBERS_IN_WORDS", _pdf("Replace twelve seals."))
    assert status == "FAIL"
    assert suggestions[0].proposed == "12 seals"
    assert _run("S1000D_NUMBERS_IN_WORDS", _pdf("Refer to step 3 and Figure 2 for 4 mm gaps."))[0] == "PASS"


def test_procedure_sub_steps_use_letters_not_dashes() -> None:
    good = "Main procedure\n(1) Remove the cover.\n(a) Loosen the screws.\nRequirements after job completion\n"
    bad = "Main procedure\n(1) Remove the cover.\n- Loosen the screws.\n- Lift the cover.\nRequirements after job completion\n"
    outside = "Preliminary requirements\n- List item outside the procedure.\n"
    assert _run("S1000D_PROCEDURE_LIST_STYLE", _pdf(good))[0] == "PASS"
    assert _run("S1000D_PROCEDURE_LIST_STYLE", _pdf(outside))[0] == "PASS"
    status, suggestions = _run("S1000D_PROCEDURE_LIST_STYLE", _pdf(bad))
    assert status == "FAIL"
    assert [item.proposed for item in suggestions] == ["(a) Loosen the screws.", "(b) Lift the cover."]


def test_job_setup_with_several_paragraphs_needs_preliminary_conditions() -> None:
    several = "Job set up\n(1) Get the tools.\n(2) Prepare the area.\nMain procedure\n"
    with_conditions = "Job set up\n(1) Preliminary conditions\n(2) Prepare the area.\nMain procedure\n"
    single = "Job set up\n(1) Get the tools.\nMain procedure\n"
    assert _run("S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS", _pdf(several))[0] == "FAIL"
    assert _run("S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS", _pdf(with_conditions))[0] == "PASS"
    assert _run("S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS", _pdf(single))[0] == "PASS"
    assert _run("S1000D_JOB_SETUP_PRELIMINARY_CONDITIONS", _pdf("No job set up here"))[0] == "PASS"


def test_job_setup_tooling_table_can_only_be_flagged_for_verification() -> None:
    with_table = "Job set up\nTooling complementary information\nTool Qty\nMain procedure\n"
    without_table = "Job set up\n(1) Get the tools.\nMain procedure\n"
    assert _run("S1000D_JOB_SETUP_TOOLING_TABLE", _pdf(with_table))[0] == "PASS"
    assert _run("S1000D_JOB_SETUP_TOOLING_TABLE", _pdf(without_table))[0] == "INCONCLUSIVE"
    assert _run("S1000D_JOB_SETUP_TOOLING_TABLE", _pdf("Nothing"))[0] == "PASS"


def test_breakdown_table_follows_the_template_columns() -> None:
    good = (
        "Table DESC-3 Composition Table C16786CA01\nNomenclature\nPart Number\nAmendment Status\n"
        ". A B C D E F\nEquipment\nDesignator\nATA No.\nISI C16786CA01 34-22-42"
    )
    bad = "Table DESC-3 Composition Table C16786CA01\nNomenclature\nPart Number\nATA No.\n"
    assert _run("S1000D_DETAILED_BREAKDOWN_TABLE", _pdf(good))[0] == "PASS"
    assert _run("S1000D_DETAILED_BREAKDOWN_TABLE", _pdf(bad))[0] == "FAIL"
    assert _run("S1000D_DETAILED_BREAKDOWN_TABLE", _pdf("no table"))[0] == "PASS"


def test_storage_page_has_no_temperature_besides_the_note_reference() -> None:
    note = (
        "NOTE\nDuring storage operations, make sure that the environmental conditions are as follows:\n"
        "- Temperature:Refer to SPM 20-02-00 - STANDARD PRACTICES MANUAL (SPM),\n"
        "Refer to F9111CMON-A-20-02-00-00A-812A-A - Storage and Transportation of Assemblies.\n"
    )
    assert _run("S1000D_STORAGE_NO_OTHER_TEMPERATURE", _pdf(note))[0] == "PASS"
    status, suggestions = _run(
        "S1000D_STORAGE_NO_OTHER_TEMPERATURE", _pdf(note + "Keep the temperature below 40 deg. C.\n")
    )
    assert status == "FAIL"
    assert suggestions[0].original == "Keep the temperature below 40 deg. C."
    assert _run("S1000D_STORAGE_NO_OTHER_TEMPERATURE", _pdf("Temperature: 20 deg. C"))[0] == "PASS"


def test_loctite_grade_matches_the_screw_size() -> None:
    assert _run("S1000D_LOCTITE_SCREW_SIZE", _pdf("Apply Loctite 221 on the M3 screws."))[0] == "PASS"
    assert _run("S1000D_LOCTITE_SCREW_SIZE", _pdf("Apply Loctite 222 on the M6 screws."))[0] == "PASS"
    assert _run("S1000D_LOCTITE_SCREW_SIZE", _pdf("Apply Loctite 221 on the M5 screws."))[0] == "PASS"
    status, suggestions = _run("S1000D_LOCTITE_SCREW_SIZE", _pdf("Apply Loctite 221 on the M6 screws."))
    assert status == "FAIL"
    assert suggestions[0].proposed == "Apply Loctite 222 on the M6 screws."
    assert _run("S1000D_LOCTITE_SCREW_SIZE", _pdf("Apply Loctite 222 on the M3 screws."))[0] == "FAIL"


# ------------------------------------------------------ engine integration


def test_enabled_s1000d_rules_run_through_the_engine_and_disabled_ones_do_not() -> None:
    import json

    from sqlalchemy import select

    from app.core.rules_engine import load_compiled_rules, run_all
    from app.db.models import Standard, StandardVersion
    from app.db.session import SessionLocal

    class _Doc:
        target_unit_system = "none"
        document_language = "en"
        client_metadata: dict[str, Any] = {}

    with SessionLocal() as session:
        version = session.scalar(
            select(StandardVersion).join(Standard).where(Standard.code == "THALES-S1000D")
        )
        assert version is not None
        original = version.disabled_rule_codes
        try:
            assert set(json.loads(original)) == set(_DEFINITIONS)
            assert load_compiled_rules(session, [version], checklist_enabled=False) == []

            version.disabled_rule_codes = json.dumps(
                sorted(set(_DEFINITIONS) - {"S1000D_SHOP_VERIFICATION"})
            )
            session.commit()
            loaded = load_compiled_rules(session, [version], checklist_enabled=False)
            assert [rule.id for rule in loaded] == ["S1000D_SHOP_VERIFICATION"]

            suggestions = run_all(_pdf("Testing and fault isolation only."), _Doc(), session, [version])
            assert {item.rule_code for item in suggestions} == {"S1000D_SHOP_VERIFICATION"}
            assert not run_all(_pdf("Shop Verification: done."), _Doc(), session, [version])
        finally:
            version.disabled_rule_codes = original
            session.commit()

def test_analysis_follows_catalogs_published_after_the_document_upload() -> None:
    from fastapi import Request
    from sqlalchemy import select

    from app.checks.client_registry import active_standard_versions
    from app.checks.mode_registry import analysis_standard_version_ids
    from app.db.models import Standard, StandardVersion
    from app.db.session import SessionLocal
    from app.main import create_app

    request = Request({"type": "http", "app": create_app()})
    with SessionLocal() as db:
        versions = active_standard_versions(db, request.app.state.client_configuration)
        active_ids = [str(version.id) for version in versions]
        s1000d_id = next(str(v.id) for v in versions if v.standard.code == "THALES-S1000D")
        uploaded_before = [version_id for version_id in active_ids if version_id != s1000d_id]

        assert set(analysis_standard_version_ids(request, db, uploaded_before, None)) == set(active_ids)

        mat10000 = db.scalar(
            select(StandardVersion).join(Standard).where(Standard.code == "MAT10000")
        )
        assert mat10000 is not None
        assert analysis_standard_version_ids(request, db, [str(mat10000.id)], None) == [
            str(mat10000.id)
        ]