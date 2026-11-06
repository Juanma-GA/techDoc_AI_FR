"""THALES S1000D norm: catalog contract and rule behaviour on synthetic PDF text."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.checks.client_registry import load_active_client_configuration
from app.checks.thales_rules.s1000d.norm_detector import suggest_metadata
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfLink, PdfVectorPrimitive, Span

_BUNDLE = load_active_client_configuration().bundle
_DEFINITIONS = {
    definition.code: definition
    for definition in _BUNDLE.rules
    if definition.bundle_code == "s1000d"
}

_REVISION_META = {
    "meta_revision_date": "2026-10-30",
    "meta_revision_number": "05",
    "meta_first_issue_date": "2000",
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
    # The rule's own gating condition (update type, manufacturer) is satisfied unless a test overrides it.
    condition = _DEFINITIONS[code].compiled_rule.only_if
    if condition is not None and condition.equals is not None:
        meta.setdefault(condition.field, condition.equals)
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


def test_catalog_contains_37_automatable_rules_with_translations() -> None:
    assert len(_DEFINITIONS) == 37
    for definition in _DEFINITIONS.values():
        assert definition.code.startswith("S1000D_")
        assert definition.compiled_rule.origin_ref == f"THALES-S1000D:v1:{definition.code}"
        assert definition.description and definition.message
        assert {"description", "message"} <= set(definition.translations["en"])
        assert not definition.preparation
    assert {definition.bundle_label for definition in _DEFINITIONS.values()} == {"S1000D"}


def test_s1000d_catalog_is_enabled_by_default_like_ata100() -> None:
    specs = _BUNDLE.standard_specs
    assert "default_disabled_rule_codes_by_version" not in specs["THALES-S1000D"]
    assert "default_disabled_rule_codes_by_version" not in specs["THALES-CUSTOM"]
    assert {rule.bundle_code for rule in _BUNDLE.rules} == {"ata100", "s1000d", "ste100_rules"}


def test_unknown_control_is_rejected() -> None:
    operation = _BUNDLE.operations["s1000d_content"]
    runtime = SimpleNamespace(parsed_pdf=_pdf("x"), is_docx=False, document=None)
    with pytest.raises(ValueError, match="known control"):
        operation.execute(SimpleNamespace(runtime=runtime, targets=()), {"control": "nope"})


@pytest.mark.parametrize(
    ("status", "expected"),
    [("C", "PASS"), ("R", "PASS"), ("S", "FAIL"), ("", "FAIL")],
)
def test_highlights_rfu_requires_loedm_status_c_or_r(
    status: str,
    expected: str,
) -> None:
    dmc = "F9111CMON-A-72-00-00-00A-500A-A"
    highlights = f"HIGHLIGHTS\n{dmc}\nReason for update\nChanged procedure.\n"
    pdf = _pdf(
        pages=[
            ParsedPage(page=1, text=_loedm(dm2_status=status)),
            ParsedPage(page=2, text=highlights),
        ]
    )

    result, _suggestions = _run("S1000D_HIGHLIGHTS_RFU_STATUS", pdf)

    assert result == expected


def test_highlights_rfu_status_is_inconclusive_without_readable_loedm() -> None:
    dmc = "F9111CMON-A-72-00-00-00A-500A-A"
    pdf = _pdf(f"HIGHLIGHTS\n{dmc}\nReason for update\nChanged procedure.")

    assert _run("S1000D_HIGHLIGHTS_RFU_STATUS", pdf)[0] == "INCONCLUSIVE"


def test_highlights_without_rfu_still_requires_readable_document_structure() -> None:
    pdf = _pdf(pages=[
        ParsedPage(page=1, text=_LOEDM),
        ParsedPage(page=2, text="HIGHLIGHTS\nNo updates."),
    ])

    assert _run("S1000D_HIGHLIGHTS_RFU_STATUS", pdf)[0] == "PASS"


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
    meta = {"meta_revision_date": "2026-10-30", "meta_first_issue_date": "2000"}
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
    assert len(suggestions) == 1
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


def test_copyright_year_accepts_four_digit_first_issue_year() -> None:
    statement = (
        "\u00a9 2024-2026 THALES AVS FRANCE SAS. This document and any data included are the "
        "property of THALES AVS FRANCE SAS. They cannot be reproduced, disclosed or used "
        "without the company's prior written approval"
    )

    assert _run(
        "S1000D_DATA_RESTRICTION_COPYRIGHT",
        _pdf(statement),
        **{**_REVISION_META, "meta_first_issue_date": "2024"},
    )[0] == "PASS"


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
            assert set(json.loads(original)) == set()
            assert {rule.id for rule in load_compiled_rules(session, [version], checklist_enabled=False)} == set(
                _DEFINITIONS
            )

            version.disabled_rule_codes = json.dumps(
                sorted(set(_DEFINITIONS) - {"S1000D_SHOP_VERIFICATION"})
            )
            session.commit()
            loaded = load_compiled_rules(session, [version], checklist_enabled=False)
            assert [rule.id for rule in loaded] == ["S1000D_SHOP_VERIFICATION"]

            def s1000d_pdf(text: str) -> ParsedPdf:
                return _pdf(
                    pages=[ParsedPage(page=1, text=_LOEDM), ParsedPage(page=2, text=text)]
                )

            def s1000d_codes(pdf: ParsedPdf) -> set[str]:
                suggestions = run_all(pdf, _Doc(), session, [version])
                return {item.rule_code for item in suggestions if item.rule_code.startswith("S1000D_")}

            assert s1000d_codes(s1000d_pdf("Testing and fault isolation only.")) == {"S1000D_SHOP_VERIFICATION"}
            assert not s1000d_codes(s1000d_pdf("Shop Verification: done."))
            # Not an S1000D publication (no LOEDM): the S1000D rules do not apply.
            assert not s1000d_codes(_pdf("Testing and fault isolation only."))
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


# ------------------------------------------- published layout (Thales CMP, S1000D 4.2)

_DMC_CONFIGURATION = "F9111FCTN-A-22-15-10-00A-020A-D"
_DMC_DISASSEMBLY = "F9111FCTN-A-22-15-10-00A-500A-A"
_PAGE_HEADER = "COMPONENT MAINTENANCE PUBLICATION\nF9111FCTN-F9111-C0044-00\nC13088 Series\n"

# The title precedes the DMC, which the renderer wraps after the model identification code.
_REAL_LOEDM = (
    _PAGE_HEADER
    + "LIST OF EFFECTIVE DATA MODULES\n"
    "The LOEDM reflects the status of the data modules used within this publication.\n"
    "Data module title\nData module code\nIssue \nnumber\nIssue Date\nStatus\n"
    "FLIGHT CONTROL MODULE (FCM) \n- Configuration\nF9111FCTN-\nA-22-15-10-00A-020A-D\n002\n2026-01-29\nC\n"
    "Generic - Copyright\nF9111GENE-\nA-00-00-00-00A-021A-D\n003\n2026-01-14\n"
    "FLIGHT CONTROL MODULE (FCM) \n- Disassembly\nF9111FCTN-\nA-22-15-10-00A-500A-A\n002\n2026-01-29\nC\n"
    "FLIGHT CONTROL MODULE (FCM) \n- IPD Figure 01\nF9111FCTN-\nA-22-15-10-010-941A-D\n002\n2026-01-29\n"
    "22-15-10\nLIST OF EFFECTIVE DATA MODULES\n2026-01-29\nPage LOEDM-1\n"
)


def _filled_bar(x0: float, x1: float, top: float, bottom: float) -> list[PdfVectorPrimitive]:
    """A revision bar as exported by the publishing chain: a black-filled rectangle split in four lines."""
    black = (0.0, 0.0, 0.0)

    def side(bbox: tuple[float, float, float, float]) -> PdfVectorPrimitive:
        return PdfVectorPrimitive(kind="line", bbox=bbox, color=None, fill=black, width=0.0)

    return [
        side((x0, top, x1, top)),
        side((x1, top, x1, bottom)),
        side((x0, bottom, x1, bottom)),
        side((x0, top, x0, bottom)),
    ]


def test_loedm_is_read_with_the_title_before_a_wrapped_dmc() -> None:
    from app.checks.thales_rules.s1000d.data_modules import parse_loedm

    rows, pages = parse_loedm([ParsedPage(page=1, text=_REAL_LOEDM)])
    assert pages == [1]
    assert [(row.dmc, row.status, row.generic) for row in rows] == [
        (_DMC_CONFIGURATION, "C", False),
        ("F9111GENE-A-00-00-00-00A-021A-D", None, True),
        (_DMC_DISASSEMBLY, "C", False),
        ("F9111FCTN-A-22-15-10-010-941A-D", None, False),
    ]
    assert [str(row.issue_date) for row in rows] == [
        "2026-01-29",
        "2026-01-14",
        "2026-01-29",
        "2026-01-29",
    ]
    assert rows[0].title == "FLIGHT CONTROL MODULE (FCM) - Configuration"


def test_information_codes_may_contain_letters() -> None:
    from app.checks.thales_rules.s1000d.data_modules import DMC_RE

    # 00T is the information code of the change record.
    assert DMC_RE.fullmatch("F9111FCTN-A-22-15-10-00A-00TA-D")
    assert DMC_RE.fullmatch("F9111FCTN-A-22-15-10-010-941A-D")


def test_month_day_year_dates_are_understood() -> None:
    from app.checks.thales_rules.s1000d.data_modules import IssueDate, parse_issue_date

    assert parse_issue_date("DEC 15, 2026") == IssueDate(2026, 12, 15)
    assert parse_issue_date("DEC 15/26") == IssueDate(2026, 12, 15)


def test_pages_are_mapped_from_dm_start_and_end_markers() -> None:
    from app.checks.thales_rules.s1000d.data_modules import dm_page_map, parse_loedm

    highlights = (
        _PAGE_HEADER
        + "HIGHLIGHTS\nThe listed changes are introduced in issue 005.\n"
        "Data module/Technical publication\nReason for update\nPage number\n"
        f"{_DMC_CONFIGURATION}\nMigration ATA 2200 en S1000D 4.2\nCONF-1\n"
    )
    pages = [
        ParsedPage(page=1, text=_REAL_LOEDM),
        ParsedPage(page=2, text=highlights),
        ParsedPage(page=3, text=_PAGE_HEADER + f"Configuration\n{_DMC_CONFIGURATION}\n1. Product configuration"),
        ParsedPage(page=4, text=f"More text\n {_DMC_CONFIGURATION}\nEnd of\n22-15-10\nCONFIGURATION"),
        ParsedPage(page=5, text=_PAGE_HEADER + "Servicing\nSERVC-1 Specific support equipment"),
        ParsedPage(page=6, text=_PAGE_HEADER + f"{_DMC_DISASSEMBLY}\n1. Disassembly"),
    ]
    rows, loedm_pages = parse_loedm(pages)
    assert dm_page_map(pages, rows, loedm_pages) == {
        3: _DMC_CONFIGURATION,
        4: _DMC_CONFIGURATION,
        6: _DMC_DISASSEMBLY,
    }


def test_revision_bar_drawn_as_a_filled_rectangle_is_detected_but_not_a_table_border() -> None:
    from app.checks.thales_rules.s1000d.data_modules import revision_bars

    def border(x: float) -> PdfVectorPrimitive:
        return PdfVectorPrimitive(
            kind="line", bbox=(x, 460.0, x, 500.0), color=None, fill=(0.0, 0.0, 0.0), width=0.0
        )

    def page(primitives: list[PdfVectorPrimitive]) -> ParsedPage:
        return ParsedPage(
            page=1,
            text="x",
            spans=[Span(text="Body", bbox=(70.0, 300.0, 200.0, 312.0), page=1, font="Arial", size=10.0)],
            page_width=600.0,
            page_height=800.0,
            vector_primitives=primitives,
        )

    bars = revision_bars(page([*_filled_bar(38.8, 42.5, 300.0, 312.0), border(51.0), border(51.8)]))
    assert len(bars) == 1
    assert 40.0 < bars[0].x < 41.5
    assert not revision_bars(page([border(51.0), border(51.8)]))


def test_rfu_of_a_changed_dm_is_read_from_the_highlights_page() -> None:
    highlights = (
        _PAGE_HEADER
        + "HIGHLIGHTS\nThe listed changes are introduced in issue 005.\n"
        "Data module/Technical publication\nReason for update\nPage number\n"
        f"{_DMC_CONFIGURATION}\nMigration ATA 2200 en S1000D 4.2\nCONF-1\n"
    )
    pdf = _pdf(
        pages=[
            ParsedPage(page=1, text=_REAL_LOEDM),
            ParsedPage(page=2, text=highlights),
            _bar_page(3, f"{_DMC_CONFIGURATION}\nConfiguration", bar=True),
            _bar_page(4, f"{_DMC_DISASSEMBLY}\nDisassembly", bar=True),
        ]
    )
    status, suggestions = _run("S1000D_CHANGED_DM_REVISION_BARS", pdf)
    assert status == "FAIL"
    assert [item.page for item in suggestions] == [4]


def test_published_title_block_is_checked_against_the_mapping() -> None:
    cover = "Manufacturer Code: F9111\nIssue No: 005\n2026-01-29\nPage TP-1"
    meta = {"meta_revision_date": "2026-01-29", "meta_revision_number": "005"}
    assert _run(
        "S1000D_ISSUE_NUMBER_TITLE_PAGE",
        _pdf(cover),
        meta_revision_number=meta["meta_revision_number"],
    )[0] == "PASS"
    assert _run(
        "S1000D_REVISION_DATE_TITLE_PAGE",
        _pdf(cover),
        meta_revision_date=meta["meta_revision_date"],
    )[0] == "PASS"
    outdated = cover.replace("005", "004").replace("2026-01-29", "2026-01-14")
    assert _run(
        "S1000D_ISSUE_NUMBER_TITLE_PAGE",
        _pdf(outdated),
        meta_revision_number=meta["meta_revision_number"],
    )[0] == "FAIL"
    assert _run(
        "S1000D_REVISION_DATE_TITLE_PAGE",
        _pdf(outdated),
        meta_revision_date=meta["meta_revision_date"],
    )[0] == "FAIL"


def _identity_page(page_number: int, header: str, footer: str | None = None) -> ParsedPage:
    header_spans = [
        Span(
            text=line,
            bbox=(40.0, 40.0 + index * 20.0, 300.0, 55.0 + index * 20.0),
            page=page_number,
            font="Arial",
            size=10.0,
        )
        for index, line in enumerate(header.splitlines())
    ]
    text_parts = [header]
    spans = header_spans
    if footer is not None:
        text_parts.append(footer)
        spans = [
            *header_spans,
            Span(
                text=footer,
                bbox=(40.0, 760.0, 300.0, 780.0),
                page=page_number,
                font="Arial",
                size=8.0,
            ),
        ]
    return ParsedPage(
        page=page_number,
        text="\n".join(text_parts),
        spans=spans,
        page_width=600.0,
        page_height=800.0,
    )


def test_cmm_number_matches_the_first_page_even_when_printed_in_the_header() -> None:
    expected = "22-15-10"
    correct = _pdf(pages=[_identity_page(1, f"{expected}\nIssue No: 006")])
    incorrect = _pdf(pages=[_identity_page(1, "22-15-11\nIssue No: 006")])

    assert _run("S1000D_CMM_NUMBER_TITLE_PAGE", correct, meta_cmm_number=expected)[0] == "PASS"
    assert _run("S1000D_CMM_NUMBER_TITLE_PAGE", incorrect, meta_cmm_number=expected)[0] == "FAIL"
    assert _run(
        "S1000D_CMM_NUMBER_TITLE_PAGE",
        _pdf(pages=[_identity_page(1, "Issue No: 006")]),
        meta_cmm_number=expected,
    )[0] == "FAIL"


def test_cmm_number_must_match_in_every_detected_footer() -> None:
    expected = "22-15-10"
    title = _identity_page(1, f"{expected}\nIssue No: 006\n2026-09-22", "2026-09-22")
    matching = _pdf(
        pages=[
            title,
            _identity_page(2, "Document content", expected),
            _identity_page(3, "Document content", expected),
        ]
    )
    mismatching = _pdf(
        pages=[
            title,
            _identity_page(2, "Document content", expected),
            _identity_page(3, "Document content", "22-15-11"),
        ]
    )

    assert _run("S1000D_CMM_NUMBER_FOOTERS", matching, meta_cmm_number=expected)[0] == "PASS"
    assert _run("S1000D_CMM_NUMBER_FOOTERS", mismatching, meta_cmm_number=expected)[0] == "FAIL"


def test_s1000d_mapping_and_detection_use_iso_revision_dates() -> None:
    field = _BUNDLE.mapping_for_norm("s1000d").fields["meta_revision_date"]
    assert field.pattern == r"^\d{4}-\d{2}-\d{2}$"
    assert field.max_length == 10
    assert suggest_metadata(["Issue No: 006\n2026-09-22"])["meta_revision_date"] == "2026-09-22"


def test_revision_date_must_match_the_issue_date_on_the_first_page() -> None:
    expected = "2026-09-22"
    correct = _pdf("Issue No: 006\n2026-09-22")
    incorrect = _pdf("Issue No: 006\n2026-09-23")
    incomplete = _pdf("Issue No: 006\n2026-09")
    missing = _pdf("Issue No: 006")
    only_on_second_page = _pdf("Issue No: 006", "Issue date: 2026-09-22")

    assert _run("S1000D_REVISION_DATE_TITLE_PAGE", correct, meta_revision_date=expected)[0] == "PASS"
    assert _run("S1000D_REVISION_DATE_TITLE_PAGE", incorrect, meta_revision_date=expected)[0] == "FAIL"
    assert _run("S1000D_REVISION_DATE_TITLE_PAGE", incomplete, meta_revision_date=expected)[0] == "FAIL"
    assert _run("S1000D_REVISION_DATE_TITLE_PAGE", missing, meta_revision_date=expected)[0] == "FAIL"
    assert _run(
        "S1000D_REVISION_DATE_TITLE_PAGE",
        only_on_second_page,
        meta_revision_date=expected,
    )[0] == "FAIL"


def test_issue_number_must_match_issue_no_on_the_first_page() -> None:
    expected = "06"
    correct = _pdf(pages=[_identity_page(1, "22-15-10\nIssue No: 006")])
    incorrect = _pdf(
        pages=[
            _identity_page(1, "22-15-10\nIssue No: 005"),
            _identity_page(2, "Issue No: 006"),
        ]
    )
    missing = _pdf(pages=[_identity_page(1, "22-15-10"), _identity_page(2, "Issue No: 006")])

    assert _run("S1000D_ISSUE_NUMBER_TITLE_PAGE", correct, meta_revision_number=expected)[0] == "PASS"
    assert _run("S1000D_ISSUE_NUMBER_TITLE_PAGE", incorrect, meta_revision_number=expected)[0] == "FAIL"
    assert _run("S1000D_ISSUE_NUMBER_TITLE_PAGE", missing, meta_revision_number=expected)[0] == "FAIL"


def test_change_record_is_the_record_of_revisions_of_the_published_layout() -> None:
    change = "Change record\n1. List of revisions\nTable\nIssue Number\nIssue Date\n005\nDEC 15, 2026\n"
    assert _run(
        "S1000D_MCO_REVISION_ROW",
        _pdf("cover", change),
        meta_revision_date="2026-12-15",
        meta_revision_number="005",
    )[0] == "PASS"
    assert _run(
        "S1000D_MCO_REVISION_ROW",
        _pdf("cover", change),
        meta_revision_date="2026-01-29",
        meta_revision_number="005",
    )[0] == "FAIL"


def test_migration_date_rule_leaves_generic_dms_alone() -> None:
    pdf = _pdf(_REAL_LOEDM)
    assert _run("S1000D_MIGRATION_DM_DATES", pdf, meta_revision_date="2026-01-29")[0] == "PASS"
    status, suggestions = _run("S1000D_MIGRATION_DM_DATES", pdf, meta_revision_date="2026-09-22")
    assert status == "FAIL"
    assert [item.original for item in suggestions] == [
        _DMC_CONFIGURATION,
        _DMC_DISASSEMBLY,
        "F9111FCTN-A-22-15-10-010-941A-D",
    ]
    assert _run("S1000D_MIGRATION_LOEDM_STATUS", pdf)[0] == "FAIL"  # the IPD figure has no status


def test_procedure_heading_of_the_published_layout() -> None:
    good = "A.\nJob description\n- Cleaning of the unit\nC.\nProcedure\n(1) Do it.\n(a) Loosen.\nD.\nClose up\n- Outside\n"
    bad = "C.\nProcedure\n(1) Remove the cover.\n- Loosen the screws.\nD.\nClose-up\nNot applicable\n"
    assert _run("S1000D_PROCEDURE_LIST_STYLE", _pdf(good))[0] == "PASS"
    status, suggestions = _run("S1000D_PROCEDURE_LIST_STYLE", _pdf(bad))
    assert status == "FAIL"
    assert [item.proposed for item in suggestions] == ["(a) Loosen the screws."]


def test_size_designations_are_not_numbers_to_spell_out() -> None:
    assert _run("S1000D_NUMBERS_IN_WORDS", _pdf("The ARINC 600 Size 2 connector."))[0] == "PASS"
    assert _run("S1000D_NUMBERS_IN_WORDS", _pdf("(b) Loosen and remove the ten screws"))[0] == "FAIL"


def test_tools_additional_information_is_a_tooling_table() -> None:
    with_table = "B.\nJob Set-up\n(1) Tools additional information\nTable\nName\nC.\nProcedure\n"
    assert _run("S1000D_JOB_SETUP_TOOLING_TABLE", _pdf(with_table))[0] == "PASS"
    assert _run("S1000D_JOB_SETUP_TOOLING_TABLE", _pdf(with_table.replace("Tools additional information", "Tools")))[0] == "INCONCLUSIVE"


def test_not_specific_table_cell_must_be_followed_by_the_local_mfr() -> None:
    good = "Ammeter\nNot specific\nCommercially \navailable\nBNG bench\nBS1-1-1\nF9111\nTool (Ammeter (Not specific))\n"
    bad = "Voltmeter\nNot specific\nF9111\n1\n"
    assert _run("S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF", _pdf(good))[0] == "PASS"
    assert _run("S1000D_SUPPORT_EQUIPMENT_LOCAL_MNF", _pdf(bad))[0] == "FAIL"


def test_first_verification_is_tabtop_in_the_published_rendering() -> None:
    outdated = "(1) Testing and Fault Isolation: Shop check which is done by performance (OCT 30/2005).\n"
    updated = "The shop verification will be done at the first repair of the equipment.\n"
    assert _run("S1000D_QA_FIRST_VERIFICATION", _pdf(updated))[0] == "PASS"
    status, suggestions = _run("S1000D_QA_FIRST_VERIFICATION", _pdf(outdated))
    assert status == "FAIL"
    assert suggestions[0].original.startswith("Shop check which is done by performance")
    assert _run("S1000D_QA_FIRST_VERIFICATION", _pdf("8. Shop Verification\nNothing"))[0] == "FAIL"


def test_copyright_footer_of_the_published_layout() -> None:
    footer = (
        "\u00a92006-2026 THALES AVS FRANCE SAS This document and any data included are the property of "
        "THALES AVS FRANCE SAS. They \ncannot be reproduced, disclosed or used without the company's "
        "prior written approval."
    )
    meta = {"meta_revision_date": "2026-01-29", "meta_first_issue_date": "2006"}
    assert _run("S1000D_DATA_RESTRICTION_COPYRIGHT", _pdf(footer), **meta)[0] == "PASS"
    assert _run("S1000D_DATA_RESTRICTION_COPYRIGHT", _pdf(footer.replace("2026", "2024", 1)), **meta)[0] == "FAIL"


_PUBLISHED_STORAGE = (
    "B.\nJob set-up\n(1) Preliminary conditions\nNOTE\n"
    "During storage operations, make sure that the environmental conditions are as \nfollows:\n"
    "- Pressure: No specific environmental level other than the ambient pressure \nlevel is necessary.\n"
    "- Relative humidity: \n \n Storage - \nGeneral procedure.\n"
    "Refer to SPM 20-02-00 - STANDARD PRACTICES \nMANUAL (SPM) Refer to F9111CMON-A-20-02-00-00A-800A-A\n"
    "- Temperature: \n \n- Storage and \nTransportation of Assemblies\n"
    "Refer to SPM 20-02-00 - STANDARD PRACTICES MANUAL \n(SPM) Refer to F9111CMON-A-20-02-00-00A-812A-A\n"
)


def test_published_storage_note_has_the_links_printed_after_its_text() -> None:
    pdf = _pdf(_PUBLISHED_STORAGE)
    for code in (
        "S1000D_STORAGE_TEMPERATURE_NOTE",
        "S1000D_STORAGE_NO_OTHER_TEMPERATURE",
        "S1000D_HUMIDITY_DM_REFERENCE",
    ):
        assert _run(code, pdf)[0] == "PASS", code
    status, suggestions = _run("S1000D_STORAGE_TEMPERATURE_NOTE", _pdf(_PUBLISHED_STORAGE.replace("812A", "8120")))
    assert status == "FAIL"


def test_outdated_humidity_reference_is_reported_on_its_text() -> None:
    outdated = (
        "3. Relative humidity: \n, \n - Storage - General procedure.\n"
        "Refer to SPM 20-02-00 - STANDARD PRACTICES MANUAL (SPM)\n"
        "Refer to F9111CMON-A-20-02-00-02000-800A-C\n"
    )
    status, suggestions = _run("S1000D_HUMIDITY_DM_REFERENCE", _pdf(outdated))
    assert status == "FAIL"
    assert suggestions[0].original == "F9111CMON-A-20-02-00-02000-800A-C"
    assert _run("S1000D_HUMIDITY_DM_REFERENCE", _pdf(outdated.replace("02000-800A-C", "00A-800A-A")))[0] == "PASS"


def test_storage_and_humidity_notes_follow_the_manufacturer() -> None:
    boeing = _PUBLISHED_STORAGE.replace("SPM", "SOPM").replace(
        "STANDARD PRACTICES", "STANDARD OVERHAUL PRACTICES"
    )
    for code in ("S1000D_STORAGE_TEMPERATURE_NOTE", "S1000D_HUMIDITY_DM_REFERENCE"):
        assert _run(code, _pdf(boeing), meta_manufacturer="Boeing")[0] == "PASS", code
        assert _run(code, _pdf(boeing), meta_manufacturer="Airbus")[0] == "FAIL", code
        assert _run(code, _pdf(_PUBLISHED_STORAGE), meta_manufacturer="Boeing")[0] == "FAIL", code


def test_loctite_without_a_screw_size_in_the_text_is_left_to_verify() -> None:
    text = "(c) Apply the \nSupply (Loctite 221 (ad-cr-007))\n to the threads of the ten screws \n"
    assert _run("S1000D_LOCTITE_SCREW_SIZE", _pdf(text))[0] == "INCONCLUSIVE"


# --------------------------------------------- gating, mapping field and norm detection


@pytest.mark.parametrize(
    ("code", "meta", "runs"),
    [
        ("S1000D_MIGRATION_DM_DATES", {"meta_update_type": "Migration"}, True),
        ("S1000D_MIGRATION_DM_DATES", {"meta_update_type": "MCO"}, False),
        ("S1000D_MIGRATION_DM_DATES", {}, False),
        ("S1000D_MCO_DM_DATES", {"meta_update_type": "mco"}, True),
        ("S1000D_MCO_REVISION_ROW", {"meta_update_type": "Migration"}, False),
        ("S1000D_MCO_LOEDM_STATUS", {"meta_update_type": "MCO"}, True),
        ("S1000D_MIGRATION_LOEDM_STATUS", {"meta_update_type": "MCO"}, False),
        ("S1000D_MIGRATION_REVISION_ISSUE", {"meta_update_type": "Migration"}, True),
        ("S1000D_SPM_LINK_AIRBUS", {"meta_manufacturer": "Airbus"}, True),
        ("S1000D_SPM_LINK_AIRBUS", {"meta_manufacturer": "Boeing"}, False),
        ("S1000D_SOPM_LINK_BOEING", {"meta_manufacturer": "Boeing"}, True),
        ("S1000D_SOPM_LINK_BOEING", {"meta_manufacturer": "Airbus"}, False),
    ],
)
def test_rules_apply_only_to_their_update_type_and_manufacturer(
    code: str, meta: dict[str, str], runs: bool
) -> None:
    document = SimpleNamespace(client_metadata=dict(meta))
    results, _ = execute_pdf_rules(
        _pdf(_LOEDM),
        [_DEFINITIONS[code].compiled_rule],
        document=document,
        client_operations=_BUNDLE.operations,
        client_entities=_BUNDLE.mapping.entities,
    )
    assert bool(results) is runs


def test_update_type_is_an_optional_mapping_field() -> None:
    field = _BUNDLE.mapping.fields["meta_update_type"]
    assert field.type == "enum"
    assert field.allowed_values == ["Migration", "MCO"]
    assert not field.required


def test_condition_equals_requires_a_present_state() -> None:
    from pydantic import ValidationError

    from app.core.compiled_rules import Condition

    with pytest.raises(ValidationError):
        Condition(field="meta_manufacturer", state="absent", equals="Boeing")


def test_the_document_norm_is_detected_from_its_loedm_and_selects_the_rules() -> None:
    from app.core.rules_engine import _keep_document_norm_rules

    norm_rules = {
        norm: [d.compiled_rule for d in _BUNDLE.rules if d.bundle_code == norm]
        for norm in ("ata100", "s1000d")
    }
    everything = [*norm_rules["ata100"], *norm_rules["s1000d"]]
    s1000d = _pdf(_REAL_LOEDM)
    classic = _pdf("LIST OF EFFECTIVE PAGES\nPage 1\nF9111CMON-A-72-00-00-00A-500A-A mentioned in the text")

    assert _BUNDLE.norm_selector(s1000d) == "s1000d"
    assert _BUNDLE.norm_selector(classic) == "ata100"
    assert _BUNDLE.default_norm == "ata100"

    warnings: list[str] = []
    kept = _keep_document_norm_rules(everything, s1000d, _BUNDLE, warnings)
    assert {rule.id for rule in kept} == {rule.id for rule in norm_rules["s1000d"]}
    assert warnings and "S1000D" in warnings[0] and "ATA100" in warnings[0]

    warnings = []
    kept = _keep_document_norm_rules(everything, classic, _BUNDLE, warnings)
    assert {rule.id for rule in kept} == {rule.id for rule in norm_rules["ata100"]}
    assert not warnings


def test_a_chosen_norm_overrides_the_detection() -> None:
    from app.core.rules_engine import _keep_document_norm_rules

    norm_rules = {
        norm: [d.compiled_rule for d in _BUNDLE.rules if d.bundle_code == norm]
        for norm in ("ata100", "s1000d")
    }
    everything = [*norm_rules["ata100"], *norm_rules["s1000d"]]

    warnings: list[str] = []
    kept = _keep_document_norm_rules(everything, _pdf(_REAL_LOEDM), _BUNDLE, warnings, norm="ata100")
    assert {rule.id for rule in kept} == {rule.id for rule in norm_rules["ata100"]}
    assert warnings == [
        "Norme choisie pour cette analyse : ATA100 (le document semble suivre S1000D). "
        "Les règles S1000D n'ont pas été exécutées."
    ]


def test_a_detected_norm_without_active_rule_is_reported() -> None:
    from app.core.rules_engine import _keep_document_norm_rules

    ata_only = [d.compiled_rule for d in _BUNDLE.rules if d.bundle_code == "ata100"]
    warnings: list[str] = []

    kept = _keep_document_norm_rules(ata_only, _pdf(_REAL_LOEDM), _BUNDLE, warnings)

    assert kept == []
    assert any("Aucune règle S1000D n'est active" in message for message in warnings)


def test_chosen_norm_runs_although_all_its_rules_are_disabled() -> None:
    import json

    from sqlalchemy import select

    from app.core.rules_engine import forced_norm_codes, load_compiled_rules, run_all
    from app.db.models import Standard, StandardVersion
    from app.db.session import SessionLocal

    class _Doc:
        target_unit_system = "none"
        document_language = "en"
        client_metadata: dict[str, Any] = {}

    pdf = _pdf(pages=[ParsedPage(page=1, text=_LOEDM), ParsedPage(page=2, text="Testing only.")])
    with SessionLocal() as session:
        version = session.scalar(
            select(StandardVersion).join(Standard).where(Standard.code == "THALES-S1000D")
        )
        assert version is not None
        original = version.disabled_rule_codes
        try:
            version.disabled_rule_codes = json.dumps(sorted(_DEFINITIONS))
            session.commit()
            assert load_compiled_rules(session, [version], checklist_enabled=False) == []
            assert forced_norm_codes(session, [version], _BUNDLE, None, checklist_enabled=False) == frozenset()
            forced = forced_norm_codes(session, [version], _BUNDLE, "s1000d", checklist_enabled=False)
            assert forced == frozenset(_DEFINITIONS)
            assert {
                rule.id
                for rule in load_compiled_rules(
                    session, [version], checklist_enabled=False, force_codes=forced
                )
            } == set(_DEFINITIONS)

            def s1000d_codes(norm: str | None, warnings: list[str]) -> set[str]:
                suggestions = run_all(pdf, _Doc(), session, [version], warnings=warnings, norm=norm)
                return {item.rule_code for item in suggestions if item.rule_code.startswith("S1000D_")}

            auto_warnings: list[str] = []
            assert not s1000d_codes(None, auto_warnings)
            assert any("Aucune règle S1000D n'est active" in message for message in auto_warnings)
            assert "S1000D_SHOP_VERIFICATION" in s1000d_codes("s1000d", [])

            # When some rules of the norm are active, the toggles are respected.
            version.disabled_rule_codes = json.dumps(
                sorted(set(_DEFINITIONS) - {"S1000D_SHOP_VERIFICATION"})
            )
            session.commit()
            assert forced_norm_codes(session, [version], _BUNDLE, "s1000d", checklist_enabled=False) == frozenset()
            assert s1000d_codes("s1000d", []) == {"S1000D_SHOP_VERIFICATION"}
        finally:
            version.disabled_rule_codes = original
            session.commit()