"""Segmentation des actions procedurales extraites en prose continue."""

from app.core.form_segmenter import segment
from app.core.ir import IRNode
from app.core.resolver import resolve
from app.core.s1000d_schema import validate_xsd
from app.core.s1000d_serializer import build_reference_index, serialize
from app.core.structure_heuristics import detect_refs
from app.core import xml_safe


def test_inline_numbered_actions_keep_intro_and_figure_references() -> None:
    text = (
        "Pour des raisons de sécurité pendant le transport, les moteurs montés "
        "verticalement sont souvent emballés et livrés en position horizontale. "
        "Pour mettre les moteurs W22 munis d’anneaux de levage (cf. Figure 4.7) "
        "en position verticale, procédez comme suit :\n"
        "1. Assurez-vous que les anneaux de levage sont bien serrés comme le "
        "montre la Figure 4.1 ;\n"
        "2. Retirez le moteur de l’emballage à l’aide des anneaux de levage "
        "montés sur la partie supérieure, comme le montre la Figure 4.10 ;"
    )
    root = IRNode(id="root", kind="section", level=0, children=[IRNode(
        id="procedure-section",
        kind="section",
        level=4,
        text="4.1.3.1 Procédures de mise en position verticale des moteurs W22",
        context="procedural",
        children=[
            IRNode(
                id="source-paragraph",
                kind="paragraph",
                text=text,
                context="procedural",
                refs=detect_refs(text) or None,
            ),
            IRNode(
                id="following-figure",
                kind="figure",
                text="Figure 4.11 Installation des anneaux de levage",
                icn="figure-4-11.jpg",
            ),
        ],
    )])
    figure_root = IRNode(id="figures", kind="section", level=0, children=[
        IRNode(id="figure-41", kind="figure", text="Figure 4.1 Anneau de levage"),
        IRNode(id="figure-47", kind="figure", text="Figure 4.7 Moteur W22"),
        IRNode(id="figure-410", kind="figure", text="Figure 4.10 Levage du moteur"),
    ])
    reference_index = build_reference_index([
        ("figures-dm", figure_root, {"dmc": "DMC-WEG-AA-00-09-00-00A-040A-A"}),
        ("procedure-dm", root, None),
    ])

    assert segment(root) == 1
    resolve(root)

    group = root.children[0].children[0]
    assert group.kind == "section"
    assert group.children[0].kind == "paragraph"
    assert group.children[0].text.rstrip().endswith("procédez comme suit :")
    steps = group.children[1]
    assert steps.kind == "item-sequence"
    assert [item.text for item in steps.children] == [
        "Assurez-vous que les anneaux de levage sont bien serrés comme le montre la Figure 4.1",
        "Retirez le moteur de l’emballage à l’aide des anneaux de levage montés sur la partie supérieure, comme le montre la Figure 4.10",
    ]
    assert [ref["target"] for ref in group.children[0].refs or []] == ["4.7"]
    assert [[ref["target"] for ref in item.refs or []] for item in steps.children] == [
        ["4.1"], ["4.10"],
    ]

    xml = serialize(
        root,
        issue="4.2",
        dm_type="procedural",
        reference_index=reference_index,
        reference_dm_id="procedure-dm",
    )
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )
    assert not [violation for violation in violations if violation["severity"] == "error"], violations

    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    main = doc.find("./content/procedure/mainProcedure")
    assert main is not None
    procedure_step = next(
        step for step in main.findall("./proceduralStep")
        if step.findtext("./title") == "Procédures de mise en position verticale des moteurs W22"
    )
    assert "procédez comme suit" in "".join(procedure_step.find("./para").itertext())
    numbered_steps = procedure_step.findall("./proceduralStep")
    assert len(numbered_steps) == 2
    assert all(step.getparent() is procedure_step for step in numbered_steps)
    assert "Assurez-vous" in "".join(numbered_steps[0].itertext())
    assert "Retirez le moteur" in "".join(numbered_steps[1].itertext())
    assert numbered_steps[1].findtext("./figure/title") == "Installation des anneaux de levage"
    assert len(doc.findall(".//content//dmRef")) == 3


def test_numbered_text_without_colon_is_not_split_as_an_announced_list() -> None:
    root = IRNode(id="root", kind="section", level=0, children=[IRNode(
        id="paragraph",
        kind="paragraph",
        text="Procédez comme suit 1. Vérifier le niveau 2. Nettoyer le carter.",
        context="procedural",
    )])

    assert segment(root) == 0
    assert root.children[0].kind == "paragraph"


def test_numbered_actions_nest_under_titled_step_without_following_figure() -> None:
    root = IRNode(id="root", kind="section", level=0, children=[IRNode(
        id="procedure-section",
        kind="section",
        level=2,
        text="Procédure",
        context="procedural",
        children=[IRNode(
            id="paragraph",
            kind="paragraph",
            text="Procédez comme suit : 1. Vérifier le niveau. 2. Contrôler la fixation.",
            context="procedural",
        )],
    )])
    assert segment(root) == 1
    resolve(root)

    xml = serialize(root, issue="4.2", dm_type="procedural")
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )
    assert not [violation for violation in violations if violation["severity"] == "error"], violations
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    main = doc.find("./content/procedure/mainProcedure")
    assert main is not None
    procedure_step = main.find("./proceduralStep")
    assert procedure_step is not None
    assert procedure_step.findtext("./title") == "Procédure"
    assert "Procédez comme suit" in "".join(procedure_step.find("./para").itertext())
    steps = procedure_step.findall("./proceduralStep")
    assert len(steps) == 2
    assert all(step.getparent() is procedure_step for step in steps)
    assert "Vérifier le niveau" in "".join(steps[0].itertext())
    assert "Contrôler la fixation" in "".join(steps[1].itertext())


def test_nested_procedure_section_keeps_actions_and_figures_in_its_parent_step() -> None:
    root = IRNode(id="root", kind="section", level=0, children=[IRNode(
        id="chapter",
        kind="section",
        level=3,
        text="4.1.3 Moteurs verticaux",
        context="procedural",
        children=[IRNode(
            id="procedure-section",
            kind="section",
            level=4,
            text="4.1.3.1 Procédures W22",
            context="procedural",
            children=[
                IRNode(
                    id="paragraph",
                    kind="paragraph",
                    text="Procédez comme suit : 1. Vérifier les anneaux. 2. Retirer le moteur.",
                    context="procedural",
                ),
                IRNode(
                    id="figure",
                    kind="figure",
                    text="Figure 4.10 Retrait du moteur",
                    icn="figure-4-10.jpg",
                ),
            ],
        )],
    )])
    assert segment(root) == 1
    resolve(root)

    xml = serialize(root, issue="4.2", dm_type="procedural")
    violations = validate_xsd(
        xml, "4.2", dm_type="procedural", allow_internal_dtd=True,
    )
    assert not [violation for violation in violations if violation["severity"] == "error"], violations
    doc = xml_safe.fromstring(xml, allow_internal_dtd=True)
    main = doc.find("./content/procedure/mainProcedure")
    assert main is not None
    chapter_step = main.find("./proceduralStep")
    assert chapter_step is not None
    assert chapter_step.findtext("./title") == "Moteurs verticaux"
    procedure_step = chapter_step.find("./proceduralStep")
    assert procedure_step is not None
    assert procedure_step.findtext("./title") == "Procédures W22"
    actions = procedure_step.findall("./proceduralStep")
    assert len(actions) == 2
    assert "Vérifier les anneaux" in "".join(actions[0].itertext())
    assert "Retirer le moteur" in "".join(actions[1].itertext())
    assert actions[1].findtext("./figure/title") == "Retrait du moteur"