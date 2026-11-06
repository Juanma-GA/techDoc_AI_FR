from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.checks.client_registry import (
    ClientConfigurationError,
    active_standard_versions,
    load_active_client_configuration,
)
from app.db.session import SessionLocal


def _write_bundle(
    root: Path,
    bundle_name: str,
    *,
    files: dict[str, str] | None = None,
    modules: dict[str, str] | None = None,
    mapping: dict[str, Any] | None = None,
    select: bool = False,
) -> None:
    bundle_dir = root / bundle_name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    payload_files = files or {"mapping": "mapping.json"}
    manifest = {
        "client_code": bundle_name.upper(),
        "label": bundle_name,
        "bundle_version": "1.0.0",
        "contract_version": "1",
        "catalogs": [{"code": "EXAMPLE", "version": "v1"}],
        "files": payload_files,
        "modules": modules or {},
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    mapping_path = payload_files.get("mapping")
    if mapping_path is not None:
        (bundle_dir / mapping_path).write_text(
            json.dumps(mapping or {"fields": {}, "entities": {}, "tokens": {}}),
            encoding="utf-8",
        )
    if select:
        (root / "active_client.json").write_text(
            json.dumps({"bundle": bundle_name}),
            encoding="utf-8",
        )


def test_repository_active_client_configuration_loads() -> None:
    configuration = load_active_client_configuration()

    assert configuration.selection.bundle == "thales_rules"
    assert configuration.selection.rule_bundles == ["ste100_rules"]
    assert configuration.manifest.client_code == "THALES"
    assert configuration.manifest.norms == ["ata100", "s1000d"]
    assert configuration.manifest.catalogs == []
    assert "meta_pnr_number" in configuration.mapping.fields
    assert configuration.mapping.fields["meta_pnr_number"].required
    assert configuration.manifest_hash
    assert configuration.mapping_hash
    assert configuration.configuration_hash
    assert configuration.bundle_hash == configuration.configuration_hash
    assert [catalog.code for catalog in configuration.bundle.catalogs] == [
        "THALES-CUSTOM",
        "THALES-S1000D",
        "ASD-STE100",
    ]
    assert len(configuration.bundle.rules) == 133
    s1000d_mapping = configuration.bundle.mapping_for_norm("s1000d")
    assert s1000d_mapping.fields["meta_revision_date"].pattern == r"^\d{4}-\d{2}-\d{2}$"
    assert s1000d_mapping.fields["meta_revision_date"].max_length == 10
    assert s1000d_mapping.fields["meta_first_issue_date"].pattern == r"^\d{4}$"
    assert s1000d_mapping.fields["meta_first_issue_date"].max_length == 4
    assert "meta_revision_number" in s1000d_mapping.fields
    assert "meta_manufacturer" in s1000d_mapping.fields
    rules_by_bundle: dict[str, list[str]] = {}
    for rule in configuration.bundle.rules:
        rules_by_bundle.setdefault(rule.bundle_code, []).append(rule.code)
    assert list(rules_by_bundle) == ["ata100", "s1000d", "ste100_rules"]
    assert [len(codes) for codes in rules_by_bundle.values()] == [89, 37, 7]
    labels = {rule.bundle_code: rule.bundle_label for rule in configuration.bundle.rules}
    assert labels == {"ata100": "ATA100", "s1000d": "S1000D", "ste100_rules": "ASD-STE100"}
    ste_rule = next(
        rule for rule in configuration.bundle.rules if rule.code == "STE_NO_MAYBE"
    )
    assert ste_rule.bundle_code == "ste100_rules"
    assert ste_rule.bundle_label == "ASD-STE100"
    assert set(configuration.bundle.operations) == {
        "revision_consistency",
        "preparation_check",
        "shop_verification",
        "storage_note_reference",
        "cmm_mapping_consistency",
        "ata100_materials",
        "ata100_lep_page_column_alignment",
        "highlights_holder",
        "highlights_document_type",
        "paragraph_justification",
        "highlights_legend_footer",
        "copyright_position",
        "page_content_position",
        "document_structure",
        "vendor_code_list",
        "pdf_bookmarks",
        "s1000d_dm_status",
        "s1000d_front_matter",
        "s1000d_content",
        "s1000d_highlights_status",
    }
    assert configuration.bundle.page_classifier is not None


def test_application_startup_does_not_discover_legacy_thales_facade(
    tmp_path: Path,
) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "sqlite:///:memory:"
    environment["STORAGE_DIR"] = str(tmp_path / "storage")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.main; "
            "assert 'app.checks.standards.thales_custom' not in sys.modules",
        ],
        cwd=backend_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_manifest_modules_build_executable_client_bundle(tmp_path: Path) -> None:
    _write_bundle(
        tmp_path,
        "synthetic_client",
        modules={
            "rules": "rules.py",
            "operations": "operations.py",
            "page_classifier": "page_classifier.py",
        },
        select=True,
    )
    bundle_dir = tmp_path / "synthetic_client"
    (bundle_dir / "rules.py").write_text(
        "from app.checks.client_bundle import ClientRuleDefinition\n"
        "from app.core.compiled_rules import Check, CompiledRule, RuleTarget\n"
        "rule = CompiledRule(id='SYNTHETIC_RULE', topic='Synthetic rule', "
        "execution='deterministic', target=RuleTarget(page='all', region='full_page'), "
        "checks=[Check(field='text', operator='client_operation', "
        "operation='synthetic_operation')], source='standard_rule')\n"
        "definition = ClientRuleDefinition(compiled_rule=rule, name='Synthetic rule', "
        "description='A rule from a manifest module.', message='Synthetic failure.', "
        "kind='content')\n"
        "RULE_DEFINITIONS = (definition,)\n"
        "STANDARD_SPEC = {'code': 'EXAMPLE', 'label': 'Example', "
        "'description': 'Synthetic client catalog.', 'versions': {'v1': [rule]}, "
        "'metadata': {'SYNTHETIC_RULE': definition.metadata}}\n",
        encoding="utf-8",
    )
    (bundle_dir / "operations.py").write_text(
        "from app.checks.client_bundle import ClientOperation, OperationResult\n"
        "def execute(context, parameters):\n"
        "    return OperationResult(status='PASS', observed='loaded')\n"
        "OPERATIONS = {'synthetic_operation': ClientOperation(" 
        "name='synthetic_operation', execute=execute)}\n",
        encoding="utf-8",
    )
    (bundle_dir / "page_classifier.py").write_text(
        "def classify_pages(parsed, document):\n"
        "    parsed.marker = 'synthetic-classifier'\n",
        encoding="utf-8",
    )

    configuration = load_active_client_configuration(tmp_path, environ={})

    assert [rule.code for rule in configuration.bundle.rules] == ["SYNTHETIC_RULE"]
    assert configuration.bundle.standard_specs["EXAMPLE"]["versions"].keys() == {"v1"}
    operation_result = configuration.bundle.operations["synthetic_operation"].execute(
        None,
        {},
    )
    assert operation_result.status == "PASS"
    assert operation_result.observed == "loaded"
    from app.core.compiled_rule_executor import execute_pdf_rules
    from app.parsers.pdf_parser import ParsedPage, ParsedPdf

    parsed_pdf = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Synthetic document")],
        full_text="Synthetic document",
        is_signed=False,
    )
    results, _suggestions = execute_pdf_rules(
        parsed_pdf,
        [configuration.bundle.rules[0].compiled_rule],
        client_operations=configuration.bundle.operations,
    )
    assert results[0].status == "PASS"
    parsed = type("Parsed", (), {})()
    configuration.bundle.page_classifier(parsed, object())
    assert parsed.marker == "synthetic-classifier"


def test_selected_rule_bundle_adds_catalog_and_group_metadata(tmp_path: Path) -> None:
    _write_bundle(tmp_path, "synthetic_client", select=True)
    (tmp_path / "active_client.json").write_text(
        json.dumps(
            {
                "bundle": "synthetic_client",
                "rule_bundles": ["synthetic_rules"],
            }
        ),
        encoding="utf-8",
    )
    addon_dir = tmp_path / "synthetic_rules"
    addon_dir.mkdir()
    (addon_dir / "manifest.json").write_text(
        json.dumps(
            {
                "label": "Synthetic rules",
                "bundle_version": "1.0.0",
                "catalogs": [{"code": "ADDON", "version": "v1"}],
                "modules": {"rules": "rules.py"},
            }
        ),
        encoding="utf-8",
    )
    (addon_dir / "rules.py").write_text(
        "from app.checks.client_bundle import ClientRuleDefinition\n"
        "from app.core.compiled_rules import Check, CompiledRule, RuleTarget\n"
        "rule = CompiledRule(id='ADDON_RULE', topic='Addon rule', "
        "execution='deterministic', target=RuleTarget(page='all', region='full_page'), "
        "checks=[Check(field='text', operator='exists', expected='required')], "
        "source='standard_rule')\n"
        "definition = ClientRuleDefinition(compiled_rule=rule, name='Addon rule', "
        "description='An additive rule.', message='Required text is missing.', "
        "kind='compiled')\n"
        "RULE_DEFINITIONS = (definition,)\n"
        "STANDARD_SPEC = {'code': 'ADDON', 'label': 'Addon', "
        "'description': 'An additive catalog.', 'versions': {'v1': [rule]}, "
        "'metadata': {'ADDON_RULE': definition.metadata}}\n",
        encoding="utf-8",
    )

    configuration = load_active_client_configuration(tmp_path, environ={})

    assert [catalog.code for catalog in configuration.bundle.catalogs] == [
        "EXAMPLE",
        "ADDON",
    ]
    assert configuration.bundle.standard_specs["ADDON"]["versions"].keys() == {"v1"}
    rule = configuration.bundle.rules[-1]
    assert rule.code == "ADDON_RULE"
    assert rule.bundle_code == "synthetic_rules"
    assert rule.bundle_label == "Synthetic rules"
    assert configuration.bundle.standard_specs["ADDON"][
        "default_disabled_rule_codes_by_version"
    ] == {"v1": ["ADDON_RULE"]}


def _write_norm_client(tmp_path: Path, norms: list[str]) -> Path:
    client_dir = tmp_path / "norm_client"
    client_dir.mkdir()
    (client_dir / "manifest.json").write_text(
        json.dumps(
            {
                "client_code": "NORM",
                "label": "Norm client",
                "bundle_version": "1.0.0",
                "contract_version": "1",
                "norms": norms,
                "files": {"mapping": "mapping.json"},
            }
        ),
        encoding="utf-8",
    )
    (client_dir / "mapping.json").write_text(
        json.dumps({"fields": {}, "entities": {}, "tokens": {}}), encoding="utf-8"
    )
    (tmp_path / "active_client.json").write_text(
        json.dumps({"bundle": "norm_client"}), encoding="utf-8"
    )
    return client_dir


def _write_norm(
    client_dir: Path,
    name: str,
    *,
    catalog: str,
    operation: str,
    default_enabled: bool | None = None,
) -> None:
    norm_dir = client_dir / name
    norm_dir.mkdir()
    manifest: dict[str, Any] = {
        "label": f"{name} norm",
        "bundle_version": "1.0.0",
        "catalogs": [{"code": catalog, "version": "v1"}],
        "modules": {
            "rules": "rules.py",
            "operations": "operations.py",
            "page_classifier": "page_classifier.py",
        },
    }
    if default_enabled is not None:
        manifest["default_enabled"] = default_enabled
    (norm_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    code = f"{name.upper()}_RULE"
    (norm_dir / "rules.py").write_text(
        "from app.checks.client_bundle import ClientRuleDefinition\n"
        "from app.core.compiled_rules import Check, CompiledRule, RuleTarget\n"
        f"rule = CompiledRule(id='{code}', topic='{code}', execution='deterministic', "
        "target=RuleTarget(page='all', region='full_page'), "
        f"checks=[Check(field='text', operator='client_operation', operation='{operation}')], "
        "source='standard_rule')\n"
        f"definition = ClientRuleDefinition(compiled_rule=rule, name='{code}', "
        "description='Norm rule.', message='Norm failure.', kind='content')\n"
        "RULE_DEFINITIONS = (definition,)\n"
        f"STANDARD_SPEC = {{'code': '{catalog}', 'label': '{catalog}', 'description': 'Norm.', "
        f"'versions': {{'v1': [rule]}}, 'metadata': {{'{code}': definition.metadata}}}}\n",
        encoding="utf-8",
    )
    (norm_dir / "operations.py").write_text(
        "from app.checks.client_bundle import ClientOperation, OperationResult\n"
        "def execute(context, parameters):\n"
        "    return OperationResult(status='PASS')\n"
        f"OPERATIONS = {{'{operation}': ClientOperation(name='{operation}', execute=execute)}}\n",
        encoding="utf-8",
    )
    (norm_dir / "page_classifier.py").write_text(
        "def classify_pages(parsed, document):\n"
        f"    parsed.calls.append('{name}')\n",
        encoding="utf-8",
    )


def test_client_norms_add_catalogs_rules_operations_and_classifiers(tmp_path: Path) -> None:
    client_dir = _write_norm_client(tmp_path, ["alpha", "beta"])
    _write_norm(client_dir, "alpha", catalog="ALPHA", operation="alpha_op", default_enabled=True)
    _write_norm(client_dir, "beta", catalog="BETA", operation="beta_op")

    bundle = load_active_client_configuration(tmp_path, environ={}).bundle

    assert [catalog.code for catalog in bundle.catalogs] == ["ALPHA", "BETA"]
    assert [(rule.code, rule.bundle_code, rule.bundle_label) for rule in bundle.rules] == [
        ("ALPHA_RULE", "alpha", "alpha norm"),
        ("BETA_RULE", "beta", "beta norm"),
    ]
    assert "default_disabled_rule_codes_by_version" not in bundle.standard_specs["ALPHA"]
    assert bundle.standard_specs["BETA"]["default_disabled_rule_codes_by_version"] == {
        "v1": ["BETA_RULE"]
    }
    assert set(bundle.operations) == {"alpha_op", "beta_op"}
    parsed = type("Parsed", (), {"calls": []})()
    assert bundle.page_classifier is not None
    bundle.page_classifier(parsed, None)
    assert parsed.calls == ["alpha", "beta"]


def test_client_norms_cannot_share_an_operation_name(tmp_path: Path) -> None:
    client_dir = _write_norm_client(tmp_path, ["alpha", "beta"])
    _write_norm(client_dir, "alpha", catalog="ALPHA", operation="shared_op")
    _write_norm(client_dir, "beta", catalog="BETA", operation="shared_op")

    with pytest.raises(ClientConfigurationError, match="operations are declared by more than one"):
        load_active_client_configuration(tmp_path, environ={})


def test_client_norms_cannot_share_a_catalog_code(tmp_path: Path) -> None:
    client_dir = _write_norm_client(tmp_path, ["alpha", "beta"])
    _write_norm(client_dir, "alpha", catalog="SAME", operation="alpha_op")
    _write_norm(client_dir, "beta", catalog="SAME", operation="beta_op")

    with pytest.raises(ClientConfigurationError, match="catalog code is selected by more than one"):
        load_active_client_configuration(tmp_path, environ={})


def test_client_manifest_needs_catalogs_or_norms_and_slug_norm_names(tmp_path: Path) -> None:
    _write_norm_client(tmp_path, [])
    with pytest.raises(ClientConfigurationError, match="catalogs or norms"):
        load_active_client_configuration(tmp_path, environ={})

    _write_norm_client_manifest = tmp_path / "norm_client" / "manifest.json"
    payload = json.loads(_write_norm_client_manifest.read_text(encoding="utf-8"))
    payload["norms"] = ["../outside"]
    _write_norm_client_manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ClientConfigurationError, match="lowercase slugs"):
        load_active_client_configuration(tmp_path, environ={})


def test_declared_rules_module_must_export_definitions(tmp_path: Path) -> None:
    _write_bundle(
        tmp_path,
        "broken_client",
        modules={"rules": "rules.py"},
        select=True,
    )
    (tmp_path / "broken_client" / "rules.py").write_text(
        "RULES = ()\n",
        encoding="utf-8",
    )

    with pytest.raises(ClientConfigurationError, match="must export RULE_DEFINITIONS"):
        load_active_client_configuration(tmp_path, environ={})


def test_repository_sample_client_runs_its_declared_rule() -> None:
    from app.core.compiled_rule_executor import execute_pdf_rules
    from app.parsers.pdf_parser import ParsedPage, ParsedPdf

    checks_dir = Path(__file__).resolve().parents[1] / "app" / "checks"
    configuration = load_active_client_configuration(
        checks_dir,
        environ={"CLIENT_BUNDLE": "sample_client"},
    )

    assert configuration.manifest.client_code == "SAMPLE"
    assert configuration.bundle.mapping.fields["part_numbers"].type == "string_list"
    assert configuration.bundle.mapping.fields["document_type"].type == "enum"
    assert configuration.bundle.mapping.fields["asset_reference"].type == "string"
    assert "sample_marker" in configuration.bundle.operations

    parsed = ParsedPdf(
        page_count=1,
        pages=[ParsedPage(page=1, text="Serial No: SN-42\nSAMPLE MARKER")],
        full_text="Serial No: SN-42\nSAMPLE MARKER",
        is_signed=False,
    )
    configuration.bundle.page_classifier(parsed, object())
    results, _suggestions = execute_pdf_rules(
        parsed,
        [definition.compiled_rule for definition in configuration.bundle.rules],
        client_operations=configuration.bundle.operations,
        client_entities=configuration.bundle.mapping.entities,
    )

    assert parsed.pages[0].page_type == "SAMPLE"
    assert results[0].status == "PASS"


def test_active_standard_versions_resolves_selected_bundle_catalogs() -> None:
    configuration = load_active_client_configuration()
    db = SessionLocal()
    try:
        versions = active_standard_versions(db, configuration)
        resolved = [(version.standard.code, version.label) for version in versions]
    finally:
        db.close()

    assert resolved == [
        ("THALES-CUSTOM", "v1"),
        ("THALES-S1000D", "v1"),
        ("ASD-STE100", "issue 7"),
    ]


def test_client_bundle_environment_variable_overrides_selection(tmp_path: Path) -> None:
    _write_bundle(tmp_path, "default_client", select=True)
    _write_bundle(tmp_path, "other_client")

    configuration = load_active_client_configuration(
        tmp_path,
        environ={"CLIENT_BUNDLE": "other_client"},
    )

    assert configuration.selection.bundle == "other_client"
    assert configuration.manifest.client_code == "OTHER_CLIENT"


def test_invalid_client_bundle_environment_override_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ClientConfigurationError, match="CLIENT_BUNDLE is invalid"):
        load_active_client_configuration(
            tmp_path,
            environ={"CLIENT_BUNDLE": 'thales"rules'},
        )


def test_manifest_must_reference_existing_files(tmp_path: Path) -> None:
    _write_bundle(
        tmp_path,
        "broken_client",
        files={"mapping": "mapping.json", "rules": "rules.py"},
        select=True,
    )

    with pytest.raises(ClientConfigurationError, match="declared file 'rules' is missing"):
        load_active_client_configuration(tmp_path, environ={})


def test_manifest_must_reference_existing_module_files(tmp_path: Path) -> None:
    _write_bundle(
        tmp_path,
        "broken_client",
        modules={"rules": "rules.py"},
        select=True,
    )

    with pytest.raises(ClientConfigurationError, match="declared file 'module:rules' is missing"):
        load_active_client_configuration(tmp_path, environ={})


def test_invalid_mapping_blocks_configuration_load(tmp_path: Path) -> None:
    _write_bundle(
        tmp_path,
        "broken_client",
        mapping={"entities": {"broken": "["}},
        select=True,
    )

    with pytest.raises(ClientConfigurationError, match="mapping file is invalid"):
        load_active_client_configuration(tmp_path, environ={})


def test_missing_selection_is_reported_when_no_environment_override_exists(
    tmp_path: Path,
) -> None:
    with pytest.raises(ClientConfigurationError, match="active_client.json is missing"):
        load_active_client_configuration(tmp_path, environ={})


def test_app_factory_propagates_invalid_client_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    def fail_load() -> None:
        raise ClientConfigurationError("invalid bundle")

    monkeypatch.setattr(main, "load_active_client_configuration", fail_load)

    with pytest.raises(ClientConfigurationError, match="invalid bundle"):
        main.create_app()


def test_app_factory_propagates_client_catalog_sync_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    def fail_sync(_db: object, _specs: object = None) -> None:
        raise ValueError("seed failed")

    monkeypatch.setattr(main, "sync_user_standard", fail_sync)

    with pytest.raises(RuntimeError, match="Client standard catalog synchronization failed"):
        main.create_app()


def test_app_factory_rejects_unsynchronized_manifest_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    def fail_resolution(_db: object, _configuration: object) -> None:
        raise ClientConfigurationError("manifest catalog is not synchronized")

    monkeypatch.setattr(main, "active_standard_versions", fail_resolution)

    with pytest.raises(RuntimeError, match="Client standard catalog synchronization failed"):
        main.create_app()