from __future__ import annotations

from typing import Any

from app.checks.client_bundle import ClientMappingField
from app.core.errors import AppError
from app.core.regex_safety import USER_REGEX_TIMEOUT_SECONDS, compile_user_regex


def validate_client_metadata_patch(
    values: dict[str, Any],
    field_definitions: dict[str, ClientMappingField],
) -> None:
    for key, value in values.items():
        definition = field_definitions.get(key)
        if definition is None:
            raise AppError(
                "CLIENT_METADATA_INVALID",
                f"Le champ de métadonnées '{key}' n'est pas déclaré par le client actif.",
                detail={"field": key, "reason": "undeclared"},
                status_code=422,
            )
        if value is None:
            continue

        if definition.type in {"string", "enum"}:
            value_is_valid = isinstance(value, str)
        elif definition.type == "string_list":
            value_is_valid = isinstance(value, list) and all(
                isinstance(item, str) for item in value
            )
        elif definition.type == "integer":
            value_is_valid = type(value) is int
        elif definition.type == "number":
            value_is_valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            value_is_valid = type(value) is bool

        if not value_is_valid:
            raise AppError(
                "CLIENT_METADATA_INVALID",
                f"Valeur invalide pour le champ de métadonnées '{key}'.",
                detail={"field": key, "expected": definition.type},
                status_code=422,
            )
        if definition.max_length is not None and len(value) > definition.max_length:
            value_is_valid = False
        if definition.max_items is not None and len(value) > definition.max_items:
            value_is_valid = False
        if definition.allowed_values is not None:
            candidates = value if definition.type == "string_list" else [value]
            if any(item not in definition.allowed_values for item in candidates):
                value_is_valid = False
        if definition.pattern is not None and value_is_valid:
            candidates = value if definition.type == "string_list" else [value]
            pattern = compile_user_regex(definition.pattern)
            try:
                if any(
                    pattern.fullmatch(item, timeout=USER_REGEX_TIMEOUT_SECONDS) is None
                    for item in candidates
                ):
                    value_is_valid = False
            except TimeoutError:
                value_is_valid = False
        if not value_is_valid:
            raise AppError(
                "CLIENT_METADATA_INVALID",
                f"Valeur invalide pour le champ de métadonnées '{key}'.",
                detail={"field": key, "expected": definition.type},
                status_code=422,
            )
