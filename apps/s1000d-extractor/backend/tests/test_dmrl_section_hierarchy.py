from __future__ import annotations

from app.core import xml_safe
from app.core.dmrl import DmrlEntry
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize
from app.core.splitter import split_by_dmrl


def test_dmrl_split_keeps_subchapter_content_and_warnings_together() -> None:
    root = IRNode(id="root", kind="section", level=0, children=[
        IRNode(id="description", kind="section", text="1 Description", level=1, children=[
            IRNode(id="subsection-1", kind="section", text="1.1 Overview", level=2, children=[
                IRNode(
                    id="warning-1",
                    kind="admonition",
                    admonition="warning",
                    text="Warning for overview.",
                ),
                IRNode(id="body-1", kind="paragraph", text="Overview content."),
            ]),
            IRNode(id="subsection-2", kind="section", text="1.2 Maintenance", level=2, children=[
                IRNode(
                    id="warning-2",
                    kind="admonition",
                    admonition="warning",
                    text="Warning for maintenance.",
                ),
                IRNode(id="body-2", kind="paragraph", text="Maintenance content."),
            ]),
        ]),
    ])

    unit = split_by_dmrl(root, [DmrlEntry(title="1 Description")])[0]
    resolve(unit.root)
    xml = serialize(unit.root, issue="4.2", dm_type="descriptive")
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    description = doc.find("./content/description/levelledPara")

    assert description is not None
    subsections = description.findall("./levelledPara")
    assert [section.findtext("./title") for section in subsections] == [
        "Overview",
        "Maintenance",
    ]
    assert description.findall("./warning") == []
    assert [
        [child.tag for child in section if isinstance(child.tag, str)]
        for section in subsections
    ] == [
        ["title", "warning", "para"],
        ["title", "warning", "para"],
    ]
    assert subsections[0].findtext("./warning/warningAndCautionPara") == "Warning for overview."
    assert subsections[0].findtext("./para") == "Overview content."
    assert subsections[1].findtext("./warning/warningAndCautionPara") == "Warning for maintenance."
    assert subsections[1].findtext("./para") == "Maintenance content."
