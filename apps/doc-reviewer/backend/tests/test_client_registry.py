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
    assert configuration.manifest.client_code == "THALES"
    assert configuration.manifest.catalogs[0].code == "THALES-CUSTOM"
    assert configuration.manifest.modules["rules"] == "rules.py"
    assert configuration.manifest.modules["operations"] == "operations.py"
    assert configuration.manifest.modules["page_classifier"] == "page_classifier.py"
    assert configuration.manifest.modules["revision_engine"] == "revision_engine.py"
    assert "meta_pnr_number" in configuration.mapping.fields
    assert configuration.manifest_hash
    assert configuration.mapping_hash
    assert configuration.configuration_hash
    assert configuration.bundle_hash == configuration.configuration_hash
    assert len(configuration.bundle.rules) == 65
    assert set(configuration.bundle.operations) == {
        "revision_consistency",
        "shop_verification",
        "highlights_holder",
        "highlights_document_type",
        "paragraph_justification",
        "highlights_legend_footer",
        "copyright_position",
        "page_content_position",
        "document_structure",
        "vendor_code_list",
        "pdf_bookmarks",
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


def test_active_standard_versions_resolves_manifest_catalogs() -> None:
    configuration = load_active_client_configuration()
    db = SessionLocal()
    try:
        versions = active_standard_versions(db, configuration)
        resolved = [(version.standard.code, version.label) for version in versions]
    finally:
        db.close()

    assert resolved == [("THALES-CUSTOM", "v1")]


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