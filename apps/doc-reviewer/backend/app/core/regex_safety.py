"""Safety policy for user-configured regular expressions."""

from typing import Any

import regex


MAX_USER_REGEX_LENGTH = 2_048
USER_REGEX_TIMEOUT_SECONDS = 0.25
USER_REGEX_INCOMPLETE_WARNING = (
    "Une ou plusieurs règles regex n'ont pas pu terminer; la couverture est réduite."
)


class UserRegexPatternError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def compile_user_regex(pattern: str, flags: int = 0) -> Any:
    if not isinstance(pattern, str) or not pattern:
        raise UserRegexPatternError("RULE_PATTERN_INVALID", "Motif regex vide ou invalide.")
    if len(pattern) > MAX_USER_REGEX_LENGTH:
        raise UserRegexPatternError(
            "RULE_PATTERN_TOO_LONG",
            f"Le motif regex dépasse la limite de {MAX_USER_REGEX_LENGTH} caractères.",
        )
    try:
        return regex.compile(pattern, flags)
    except regex.error as exc:
        raise UserRegexPatternError(
            "RULE_PATTERN_INVALID",
            f"Expression régulière invalide : {exc.msg}",
        ) from exc


def mark_user_regex_incomplete(warnings: list[str] | None) -> None:
    if warnings is not None and USER_REGEX_INCOMPLETE_WARNING not in warnings:
        warnings.append(USER_REGEX_INCOMPLETE_WARNING)