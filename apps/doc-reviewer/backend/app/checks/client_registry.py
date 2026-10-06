"""Load and validate client bundle configuration without activating it."""

from __future__ import annotations

import os
import sys
import types
import importlib.util
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.client_bundle import (
    ClientBundle,
    ClientCatalog,
    ClientMapping,
    ClientOperation,
    ClientRuleDefinition,
)
from app.db.models import Standard, StandardVersion


class ClientConfigurationError(RuntimeError):
    """Raised when the selected client configuration is incomplete or invalid."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientSelection(_StrictModel):
    bundle: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")


class ClientManifest(_StrictModel):
    client_code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    bundle_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    contract_version: str = Field(min_length=1, max_length=40)
    catalogs: list[ClientCatalog] = Field(min_length=1)
    files: dict[str, str] = Field(min_length=1)
    modules: dict[str, str] = Field(default_factory=dict)
    ui_options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_declarations(self) -> ClientManifest:
        if "mapping" not in self.files:
            raise ValueError("files must declare a mapping file")
        catalog_keys = [(catalog.code, catalog.version) for catalog in self.catalogs]
        if len(catalog_keys) != len(set(catalog_keys)):
            raise ValueError("catalog code/version pairs must be unique")
        declared_paths = {
            **self.files,
            **{f"module:{name}": path for name, path in self.modules.items()},
        }
        for role, relative_path in declared_paths.items():
            path = Path(relative_path)
            if (
                not relative_path.strip()
                or path.is_absolute()
                or ".." in path.parts
            ):
                raise ValueError(f"file path for {role} must stay inside the bundle")
        return self


@dataclass(frozen=True)
class LoadedClientConfiguration:
    selection: ClientSelection
    manifest: ClientManifest
    mapping: ClientMapping
    bundle_dir: Path
    manifest_hash: str
    mapping_hash: str
    configuration_hash: str
    bundle: ClientBundle[Any]

    @property
    def bundle_hash(self) -> str:
        return self.configuration_hash


def active_standard_versions(
    db: Session,
    configuration: LoadedClientConfiguration | None = None,
) -> list[StandardVersion]:
    """Resolve manifest catalog identifiers to their synchronized DB versions."""
    active_configuration = configuration or load_active_client_configuration()
    resolved: list[StandardVersion] = []
    for catalog in active_configuration.manifest.catalogs:
        standard = db.scalar(select(Standard).where(Standard.code == catalog.code))
        if standard is None:
            raise ClientConfigurationError(
                f"manifest catalog is not synchronized: {catalog.code}:{catalog.version}"
            )
        version = db.scalar(
            select(StandardVersion).where(
                StandardVersion.standard_id == standard.id,
                StandardVersion.label == catalog.version,
            )
        )
        if version is None:
            raise ClientConfigurationError(
                f"manifest catalog version is not synchronized: "
                f"{catalog.code}:{catalog.version}"
            )
        resolved.append(version)
    return resolved


def _read_bytes(path: Path, description: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ClientConfigurationError(f"{description} is missing or unreadable: {path}") from exc


def _parse_model(model: type[BaseModel], payload: bytes, description: str) -> Any:
    try:
        return model.model_validate_json(payload)
    except ValidationError as exc:
        raise ClientConfigurationError(f"{description} is invalid: {exc}") from exc


def _bundle_file(bundle_dir: Path, relative_path: str, role: str) -> Path:
    bundle_root = bundle_dir.resolve()
    path = (bundle_root / relative_path).resolve()
    try:
        path.relative_to(bundle_root)
    except ValueError as exc:
        raise ClientConfigurationError(f"declared file '{role}' must stay inside the bundle") from exc
    if not path.is_file():
        raise ClientConfigurationError(f"declared file '{role}' is missing: {relative_path}")
    return path


def _load_bundle_modules(
    bundle_dir: Path,
    module_paths: Mapping[str, str],
    namespace_hash: str,
) -> dict[str, types.ModuleType]:
    package_name = f"app.checks._loaded_client_{namespace_hash}"
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        package.__package__ = package_name
        package.__path__ = [str(bundle_dir)]
        package.__spec__ = importlib.util.spec_from_loader(
            package_name,
            loader=None,
            is_package=True,
        )
        sys.modules[package_name] = package

    loaded: dict[str, types.ModuleType] = {}
    for role, relative_path in module_paths.items():
        module_name = f"{package_name}.{role}"
        module_path = _bundle_file(bundle_dir, relative_path, f"module:{role}")
        module = sys.modules.get(module_name)
        if module is None or Path(getattr(module, "__file__", "")).resolve() != module_path:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ClientConfigurationError(f"module '{role}' cannot be loaded")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:  # noqa: BLE001
                sys.modules.pop(module_name, None)
                raise ClientConfigurationError(
                    f"module '{role}' failed to load: {exc}"
                ) from exc
        loaded[role] = module
    return loaded


def _build_client_bundle(
    selection: ClientSelection,
    manifest: ClientManifest,
    mapping: ClientMapping,
    bundle_dir: Path,
    manifest_hash: str,
    mapping_hash: str,
    configuration_hash: str,
) -> ClientBundle[Any]:
    namespace_hash = sha256(
        f"{configuration_hash}:{bundle_dir}".encode("utf-8")
    ).hexdigest()[:16]
    modules = _load_bundle_modules(bundle_dir, manifest.modules, namespace_hash)
    rules_module = modules.get("rules")
    operations_module = modules.get("operations")

    if "rules" in manifest.modules and not hasattr(rules_module, "RULE_DEFINITIONS"):
        raise ClientConfigurationError("rules module must export RULE_DEFINITIONS")
    raw_rules = getattr(rules_module, "RULE_DEFINITIONS", ()) if rules_module else ()
    if not isinstance(raw_rules, (list, tuple)) or any(
        not isinstance(definition, ClientRuleDefinition) for definition in raw_rules
    ):
        raise ClientConfigurationError(
            "rules module must export RULE_DEFINITIONS as ClientRuleDefinition values"
        )
    if "operations" in manifest.modules and not hasattr(operations_module, "OPERATIONS"):
        raise ClientConfigurationError("operations module must export OPERATIONS")
    operations = getattr(operations_module, "OPERATIONS", {}) if operations_module else {}
    if not isinstance(operations, Mapping) or any(
        not isinstance(operation, ClientOperation) for operation in operations.values()
    ):
        raise ClientConfigurationError(
            "operations module must export OPERATIONS as ClientOperation values"
        )

    standard_specs: dict[str, Mapping[str, Any]] = {}
    if rules_module is not None:
        exported_specs = getattr(rules_module, "STANDARD_SPECS", None)
        if exported_specs is None:
            exported_spec = getattr(rules_module, "STANDARD_SPEC", None)
            exported_specs = (
                {str(exported_spec.get("code")): exported_spec}
                if isinstance(exported_spec, Mapping)
                else {}
            )
        if not isinstance(exported_specs, Mapping):
            raise ClientConfigurationError("rules module STANDARD_SPECS must be a mapping")
        standard_specs = {str(code): spec for code, spec in exported_specs.items()}

    for catalog in manifest.catalogs:
        spec = standard_specs.get(catalog.code)
        if spec is None:
            continue
        versions = spec.get("versions")
        if not isinstance(versions, Mapping) or catalog.version not in versions:
            raise ClientConfigurationError(
                f"rules module does not define manifest catalog "
                f"{catalog.code}:{catalog.version}"
            )

    classifier = getattr(modules.get("page_classifier"), "classify_pages", None)
    if "page_classifier" in manifest.modules and not callable(classifier):
        raise ClientConfigurationError(
            "page_classifier module must export callable classify_pages"
        )

    try:
        return ClientBundle(
            client_code=manifest.client_code,
            bundle_version=manifest.bundle_version,
            contract_version=manifest.contract_version,
            manifest_hash=manifest_hash,
            mapping_hash=mapping_hash,
            bundle_hash=configuration_hash,
            catalogs=tuple(manifest.catalogs),
            mapping=mapping,
            rules=tuple(raw_rules),
            operations=dict(operations),
            standard_specs=standard_specs,
            page_classifier=classifier,
        )
    except (TypeError, ValueError) as exc:
        raise ClientConfigurationError(f"client bundle contract is invalid: {exc}") from exc


def load_active_client_configuration(
    checks_dir: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> LoadedClientConfiguration:
    """Validate active_client.json, its manifest, and all declared bundle files.

    CLIENT_BUNDLE overrides the selected bundle name. This loader intentionally
    does not resolve database catalogs or change document analysis behavior.
    """
    root = (checks_dir or Path(__file__).resolve().parent).resolve()
    variables = os.environ if environ is None else environ
    override = variables.get("CLIENT_BUNDLE")
    if override is not None:
        try:
            selection = ClientSelection(bundle=override.strip())
        except ValidationError as exc:
            raise ClientConfigurationError(f"CLIENT_BUNDLE is invalid: {exc}") from exc
    else:
        selection_payload = _read_bytes(root / "active_client.json", "active_client.json")
        selection = _parse_model(ClientSelection, selection_payload, "active_client.json")

    bundle_dir = (root / selection.bundle).resolve()
    try:
        bundle_dir.relative_to(root)
    except ValueError as exc:
        raise ClientConfigurationError("selected bundle must stay inside checks directory") from exc

    manifest_path = bundle_dir / "manifest.json"
    manifest_payload = _read_bytes(manifest_path, "manifest.json")
    manifest = _parse_model(ClientManifest, manifest_payload, "manifest.json")

    declared_payloads: dict[str, bytes] = {}
    declared_paths = {
        **manifest.files,
        **{f"module:{name}": path for name, path in manifest.modules.items()},
    }
    for role, relative_path in declared_paths.items():
        declared_path = _bundle_file(bundle_dir, relative_path, role)
        declared_payloads[role] = _read_bytes(declared_path, f"declared file '{role}'")

    mapping = _parse_model(ClientMapping, declared_payloads["mapping"], "mapping file")
    configuration_digest = sha256()
    configuration_digest.update(manifest_payload)
    for role, payload in sorted(declared_payloads.items()):
        configuration_digest.update(b"\0")
        configuration_digest.update(role.encode("utf-8"))
        configuration_digest.update(b"\0")
        configuration_digest.update(payload)

    manifest_hash = sha256(manifest_payload).hexdigest()
    mapping_hash = sha256(declared_payloads["mapping"]).hexdigest()
    configuration_hash = configuration_digest.hexdigest()
    bundle = _build_client_bundle(
        selection,
        manifest,
        mapping,
        bundle_dir,
        manifest_hash,
        mapping_hash,
        configuration_hash,
    )

    return LoadedClientConfiguration(
        selection=selection,
        manifest=manifest,
        mapping=mapping,
        bundle_dir=bundle_dir,
        manifest_hash=manifest_hash,
        mapping_hash=mapping_hash,
        configuration_hash=configuration_hash,
        bundle=bundle,
    )