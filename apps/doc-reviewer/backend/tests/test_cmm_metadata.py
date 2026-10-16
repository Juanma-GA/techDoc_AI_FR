from app.parsers.cmm_metadata import suggest_cmm_metadata_from_pages


def test_suggests_cmm_revision_and_tp1_metadata() -> None:
    suggestions = suggest_cmm_metadata_from_pages(
        [
            "HIGHLIGHTS PAGE 1\n"
            "ATA No. 80-80-01\n"
            "Revision No. 01\n"
            "Revision Date: JUL 27/26",
            "TP1\n"
            "Part Number: 1-900-SB, 1-901-SB\n"
            "Revision No. 01\n"
            "First Issue: JUL 25/95",
        ]
    )

    assert suggestions == {
        "pages_scanned": 2,
        "meta_cmm_number": "80-80-01",
        "meta_pnr_number": ["1-900-SB", "1-901-SB"],
        "meta_revision_number": "01",
        "meta_revision_date": "JUL 27/26",
        "meta_first_issue_date": "JUL 25/95",
    }


def test_extracts_revision_date_after_dated_revision_number() -> None:
    suggestions = suggest_cmm_metadata_from_pages(
        [
            "HIGHLIGHTS PAGE 1\n"
            "ATA No. 80-80-01\n"
            "REVISION No. 07 DATED MAR 14/27",
        ]
    )

    assert suggestions["meta_revision_number"] == "07"
    assert suggestions["meta_revision_date"] == "MAR 14/27"


def test_extracts_all_part_numbers_from_continuation_lines() -> None:
    suggestions = suggest_cmm_metadata_from_pages(
        [
            "HIGHLIGHTS PAGE 1",
            "TP1\n"
            "Part Number:\n"
            "1-900-SB\n"
            "1-901-SB\n"
            "1-902-SB\n"
            "1-903-SB\n"
            "Revision No. 01\n"
            "First Issue: JUL 25/95",
        ]
    )

    assert suggestions["meta_pnr_number"] == [
        "1-900-SB",
        "1-901-SB",
        "1-902-SB",
        "1-903-SB",
    ]


def test_omits_ambiguous_values_and_requires_highlights_or_tp1_context() -> None:
    suggestions = suggest_cmm_metadata_from_pages(
        [
            "HIGHLIGHTS PAGE 1\n"
            "ATA No. 80-80-01\n"
            "ATA No. 80-80-02\n"
            "Revision No. 01\n"
            "Revision No. 02\n"
            "Revision Date: JUL 27/26\n"
            "Revision Date: AUG 27/26",
            "TP1\n"
            "Part Number: 1-900-SB\n"
            "First Issue: JUL 25/95\n"
            "First Issue: AUG 25/95",
            "Title page\nATA No. 70-70-70\nRevision No. 03",
        ]
    )

    assert suggestions["meta_cmm_number"] is None
    assert suggestions["meta_revision_number"] is None
    assert suggestions["meta_revision_date"] is None
    assert suggestions["meta_first_issue_date"] is None
    assert suggestions["meta_pnr_number"] == ["1-900-SB"]


def test_returns_no_suggestions_when_labels_are_missing() -> None:
    suggestions = suggest_cmm_metadata_from_pages(
        [
            "Document title\n80-80-01\nJUL 27/26",
            "TP1\n80-80-01\nJUL 25/95",
        ]
    )

    assert suggestions["meta_cmm_number"] is None
    assert suggestions["meta_revision_number"] is None
    assert suggestions["meta_revision_date"] is None
    assert suggestions["meta_first_issue_date"] is None
    assert suggestions["meta_pnr_number"] == []
