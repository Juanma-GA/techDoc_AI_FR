"""ZIP export reference-index reuse tests."""

from types import SimpleNamespace

from app.core import ir as ir_mod
from app.core import wizard_zip_export
from app.core.ir import IRNode


def test_zip_export_builds_one_shared_reference_index(monkeypatch) -> None:
    dms = [
        {
            "dm_id": "dm-1",
            "dmc": "DMC-TEST-A-00-00-00-00A-040A-A",
            "dm_type": "descriptive",
            "tree": ir_mod.to_dict(IRNode(id="root-1", kind="section")),
        },
        {
            "dm_id": "dm-2",
            "dmc": "DMC-TEST-A-00-00-00-00A-520A-A",
            "dm_type": "procedural",
            "tree": ir_mod.to_dict(IRNode(id="root-2", kind="section")),
        },
    ]
    monkeypatch.setattr(wizard_zip_export.ws, "load_dms", lambda _doc: dms)
    monkeypatch.setattr(wizard_zip_export.wres, "dmrl_entries", lambda _doc: [])
    indexes = []
    shared_index = {("figure", "1"): []}

    def build_index(documents):
        indexes.append(documents)
        return shared_index

    monkeypatch.setattr(wizard_zip_export, "build_reference_index", build_index)
    used_indexes = []

    def generate_dm(_doc, dm_id, *, db, reference_index):
        used_indexes.append(reference_index)
        return f"<dmodule id=\"{dm_id}\"/>"

    result = wizard_zip_export.generate_zip_dm_xmls(
        SimpleNamespace(s1000d_issue="4.2"),
        ["dm-1", "dm-2"],
        db=object(),
        dm_xml_generator=generate_dm,
    )

    assert len(indexes) == 1
    assert list(result) == ["dm-1", "dm-2"]
    assert used_indexes == [shared_index, shared_index]
