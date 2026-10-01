"""Generic contracts shared by client bundles and the analysis core."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.compiled_rules import CompiledRule
from app.core.regex_safety import UserRegexPatternError, compile_user_regex


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientMappingField(_StrictModel):
    type: Literal["string", "enum", "string_list", "integer", "number", "boolean"]
    required: bool = False
    default: str | int | float | bool | list[str] | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    max_length: int | None = Field(default=None, gt=0)
    max_items: int | None = Field(default=None, gt=0)
    allowed_values: list[str] | None = None

    @model_validator(mode="after")
    def validate_field_definition(self) -> ClientMappingField:
        if self.allowed_values is not None:
            if not self.allowed_values or len(set(self.allowed_values)) != len(self.allowed_values):
                raise ValueError("allowed_values must be non-empty and unique")
            if self.type not in {"enum", "string_list"}:
                raise ValueError("allowed_values is only valid for enum and string_list fields")
        if self.type == "enum" and not self.allowed_values:
            raise ValueError("enum fields require allowed_values")
        if self.max_length is not None and self.type not in {"string", "enum"}:
            raise ValueError("max_length is only valid for string and enum fields")
        if self.max_items is not None and self.type != "string_list":
            raise ValueError("max_items is only valid for string_list fields")

        if self.default is None:
            return self
        if self.type in {"string", "enum"}:
            if not isinstance(self.default, str):
                raise ValueError(f"{self.type} fields require a string default")
            if self.type == "enum" and self.default not in (self.allowed_values or []):
                raise ValueError("enum default must be one of allowed_values")
            if self.max_length is not None and len(self.default) > self.max_length:
                raise ValueError("default exceeds max_length")
        elif self.type == "string_list":
            if not isinstance(self.default, list) or not all(
                isinstance(item, str) for item in self.default
            ):
                raise ValueError("string_list fields require a list of strings as default")
            if self.allowed_values is not None and any(
                item not in self.allowed_values for item in self.default
            ):
                raise ValueError("string_list default contains a value outside allowed_values")
            if self.max_items is not None and len(self.default) > self.max_items:
                raise ValueError("default exceeds max_items")
        elif self.type == "integer" and type(self.default) is not int:
            raise ValueError("integer fields require an integer default")
        elif self.type == "number" and (
            isinstance(self.default, bool) or not isinstance(self.default, (int, float))
        ):
            raise ValueError("number fields require a numeric default")
        elif self.type == "boolean" and type(self.default) is not bool:
            raise ValueError("boolean fields require a boolean default")
        return self


class ClientMapping(_StrictModel):
    fields: dict[str, ClientMappingField] = Field(default_factory=dict)
    entities: dict[str, str] = Field(default_factory=dict)
    tokens: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_entities(self) -> ClientMapping:
        for name, pattern in self.entities.items():
            try:
                compiled = compile_user_regex(pattern)
            except UserRegexPatternError as exc:
                raise ValueError(f"invalid entity pattern for {name}: {exc.message}") from exc
            if compiled.groups == 0:
                raise ValueError(f"entity pattern for {name} must define a capture group")
        return self


class ClientCatalog(_StrictModel):
    code: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=40)


class OperationResult(_StrictModel):
    status: Literal["PASS", "FAIL", "INCONCLUSIVE"]
    observed: str | None = None
    expected: str | None = None
    message: str | None = None
    original: str | None = None
    proposed: str | None = None
    span: tuple[int, int] | None = None
    page: int | None = Field(default=None, gt=0)
    bbox: tuple[float, float, float, float] | None = None
    bbox_strategy: Literal[
        "text",
        "empty_middle",
        "highlight_holder",
        "missing_anchor",
    ] | None = None

    @model_validator(mode="after")
    def validate_span(self) -> OperationResult:
        if self.span is not None and (self.span[0] < 0 or self.span[1] < self.span[0]):
            raise ValueError("span must be a non-negative start/end pair")
        return self


class ClientRuleDefinition(_StrictModel):
    compiled_rule: CompiledRule
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    message: str = Field(min_length=1, max_length=2000)
    kind: str = Field(min_length=1, max_length=80)
    presentation_severity: Literal["info", "warning", "error"] | None = None
    translations: dict[str, dict[str, str]] = Field(default_factory=dict)

    @property
    def code(self) -> str:
        return self.compiled_rule.id

    @property
    def metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "description": self.description,
            "kind": self.kind,
            "severity": self.presentation_severity or self.compiled_rule.severity,
            "message": self.message,
        }
        for locale, localized_fields in self.translations.items():
            for field_name, value in localized_fields.items():
                metadata[f"{field_name}_{locale}"] = value
        return metadata


ContextT = TypeVar("ContextT")


@dataclass(frozen=True)
class ClientOperationContext:
    runtime: Any
    check: Any
    targets: tuple[Any, ...]


@dataclass(frozen=True)
class ClientOperation(Generic[ContextT]):
    name: str
    execute: Callable[[ContextT, Mapping[str, Any]], OperationResult]
    suggestions: Callable[[ContextT, Mapping[str, Any]], list[OperationResult]] | None = None


@dataclass(frozen=True)
class ClientBundle(Generic[ContextT]):
    client_code: str
    bundle_version: str
    contract_version: str
    manifest_hash: str
    mapping_hash: str
    bundle_hash: str
    catalogs: tuple[ClientCatalog, ...]
    mapping: ClientMapping
    rules: tuple[ClientRuleDefinition, ...]
    operations: Mapping[str, ClientOperation[ContextT]]
    standard_specs: Mapping[str, Mapping[str, Any]]
    page_classifier: Callable[[Any, Any], None] | None = None

    def __post_init__(self) -> None:
        rule_codes = [definition.code for definition in self.rules]
        if len(rule_codes) != len(set(rule_codes)):
            raise ValueError("client bundle rule codes must be unique")
        if any(key != operation.name for key, operation in self.operations.items()):
            raise ValueError("operation registry keys must match operation names")
        unknown_operations = {
            check.operation
            for definition in self.rules
            for check in definition.compiled_rule.checks
            if check.operator == "client_operation"
            and check.operation not in self.operations
        }
        if unknown_operations:
            names = ", ".join(sorted(str(name) for name in unknown_operations))
            raise ValueError(f"client bundle references unknown operation(s): {names}")
        for definition in self.rules:
            validate_compiled_rule_mapping(definition.compiled_rule, self.mapping)
        for code, spec in self.standard_specs.items():
            if str(spec.get("code")) != code:
                raise ValueError(f"standard spec key does not match its code: {code}")


def validate_compiled_rule_mapping(rule: CompiledRule, mapping: ClientMapping) -> None:
    text_fields = {
        "text",
        "page_number",
        "document_type",
        "important_notice",
        *mapping.entities,
    }
    metadata_fields = set(mapping.fields)
    for check in rule.checks:
        if check.field not in text_fields:
            raise ValueError(f"rule {rule.id} references undeclared text field: {check.field}")
        if check.compare_to is not None:
            compare_fields = (
                metadata_fields
                if check.compare_to.source == "document_meta"
                else text_fields
            )
            if check.compare_to.field not in compare_fields:
                raise ValueError(f"rule {rule.id} references undeclared field: {check.compare_to.field}")
        if check.only_if is not None and check.only_if.field not in metadata_fields:
            raise ValueError(
                f"rule {rule.id} references undeclared metadata field: {check.only_if.field}"
            )
    if rule.only_if is not None and rule.only_if.field not in metadata_fields:
        raise ValueError(
            f"rule {rule.id} references undeclared metadata field: {rule.only_if.field}"
        )