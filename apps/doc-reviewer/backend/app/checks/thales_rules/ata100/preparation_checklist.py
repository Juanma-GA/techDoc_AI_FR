from __future__ import annotations

import hashlib
import re
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.orm import Session

from app.checks.client_bundle import ClientBundle
from app.core.checklist_compiler import compile_checklist_rule
from app.core.errors import AppError
from app.core.excel_rules import ParsedRule
from app.core.compiled_rules import CompiledRule, RuleTarget


_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_ZONE_ALIASES = {
    "page": "full_page",
    "full page": "full_page",
    "full_page": "full_page",
    "header": "header",
    "en-tête": "header",
    "entete": "header",
    "body": "body",
    "corps": "body",
    "footer": "footer",
    "pied de page": "footer",
}


def compile_preparation_checklist(
    data: bytes,
    filename: str,
    db: Session,
    client_bundle: ClientBundle,
) -> list[CompiledRule]:
    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except (InvalidFileException, OSError, ValueError) as exc:
        raise AppError(
            "PREPARATION_CHECKLIST_INVALID",
            "La checklist THALES doit être un classeur Excel lisible.",
            status_code=400,
        ) from exc
    try:
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            raise _invalid("La checklist est vide.")
        headers = [_text(value).casefold() for value in rows[0]]
        columns = {name: headers.index(name) for name in headers if name}
        required = {"code", "name", "zone", "check"}
        missing = required - columns.keys()
        if missing:
            raise _invalid("Colonnes obligatoires absentes : " + ", ".join(sorted(missing)))

        compiled: list[CompiledRule] = []
        seen: set[str] = set()
        for row_number, row in enumerate(rows[1:], start=2):
            values = {name: _cell(row, columns.get(name)) for name in headers if name}
            if not any(values.values()):
                continue
            code = values.get("code", "")
            name = values.get("name", "")
            zone = _ZONE_ALIASES.get(values.get("zone", "").casefold())
            check = values.get("check", "")
            if not _CODE_RE.fullmatch(code):
                raise _invalid(f"Code invalide à la ligne {row_number}.")
            if code in seen:
                raise _invalid(f"Code dupliqué à la ligne {row_number} : {code}.")
            if not name or not check or zone is None:
                raise _invalid(f"Nom, zone ou règle invalide à la ligne {row_number}.")
            seen.add(code)
            severity = values.get("severity", "warning").casefold() or "warning"
            if severity not in {"info", "warning", "error"}:
                raise _invalid(f"Sévérité invalide à la ligne {row_number}.")
            message = values.get("comment", "").strip() or name
            parsed = ParsedRule(
                sheet=sheet.title,
                row_number=row_number,
                check=check,
                handling="auto",
                context="",
                name=name,
                category=name,
                kind="llm_nl",
                pattern="",
                replacement="",
                target_zone=zone,
                severity=severity,
                message=message,
            )
            rule = compile_checklist_rule(
                db,
                parsed,
                filename,
                client_bundle=client_bundle,
            )
            page_types = [
                value.strip()
                for value in re.split(r"[,;|]", values.get("page_type", ""))
                if value.strip()
            ]
            target = rule.target.model_copy(
                update={
                    "page_type": page_types[0] if len(page_types) == 1 else None,
                    "page_types": page_types if len(page_types) > 1 else None,
                }
            )
            compiled.append(
                rule.model_copy(
                    update={
                        "id": code,
                        "topic": name,
                        "target": target,
                        "source_instruction": message,
                    }
                )
            )
        if not compiled:
            raise _invalid("Aucune règle exploitable n'a été trouvée.")
        return compiled
    finally:
        workbook.close()


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cell(row: tuple, column: int | None) -> str:
    return _text(row[column]) if column is not None and column < len(row) else ""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _invalid(message: str) -> AppError:
    return AppError("PREPARATION_CHECKLIST_INVALID", message, status_code=422)
