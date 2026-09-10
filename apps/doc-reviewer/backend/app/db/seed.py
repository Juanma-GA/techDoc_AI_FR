"""Seed default custom rules at startup if the `rules` table is empty.

Three demo rules wired in to give the user something to play with on a
fresh install:

1. **MISSING_SPACE_AFTER_PUNCT** — comma/period not followed by a space.
2. **ALL_CAPS_WORD** — flags 3+ consecutive uppercase letters (acronymes
   légitimes restent — l'utilisateur peut Reject).
3. **MISSING_FRENCH_ACCENT** — common French words written without their
   diacritics (déjà / être / très …).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.standards import serialize_builtin_version, user_rules
from app.db.models import Rule, Standard, StandardVersion

logger = structlog.get_logger(__name__)


_DEFAULTS = [
    {
        "name": "Pas d'oubli d'espace après ponctuation",
        "kind": "regex_replace",
        "pattern": r"([.,;:!?])(?=[A-Za-zÀ-ÿ])",
        "replacement": r"\1 ",
        "severity": "warning",
        "message": "Espace manquant après la ponctuation.",
        "enabled": True,
    },
    {
        "name": "Pas de mot en MAJUSCULES",
        "kind": "case_capitalize",
        # Match a phrase of consecutive ALL-CAPS tokens (≥4 caps each) with
        # optional French stopwords (DE / DU / LA / LE / DES / ET / …) in
        # between, so « PROCÉDURE DE MAINTENANCE » becomes a single
        # suggestion « Procédure de maintenance » rather than two unrelated
        # word-level fixes.
        "pattern": (
            r"\b[A-ZÀ-Ÿ]{4,}(?:\s+(?:DE|DU|DES|LA|LE|LES|ET|OU|AU|AUX|EN|À|À|"
            r"D'|L'|[A-ZÀ-Ÿ]{2,}))*\b"
        ),
        "replacement": "",
        "severity": "info",
        "message": "Phrase en majuscules — préférer la casse titre (Reject pour les acronymes légitimes).",
        # Desactivee par defaut : sur des docs techniques (aeronautique), l'usage
        # des majuscules est massivement legitime (WARNING/CAUTION/NOTE, titres de
        # section, acronymes, references) -> trop de faux positifs. Reste dans
        # l'onglet Regles, re-activable si besoin.
        "enabled": False,
    },
    {
        "name": "Pas d'oubli d'accent (mots FR fréquents)",
        "kind": "accent_fix",
        "pattern": (
            r"\b(?:deja|etre|ete|tres|apres|systeme|securite|verifier|"
            r"operation|piece|necessite|interet|element|donnee|donnees|"
            r"reglage|reglages|controle|procedure|generale|general|"
            r"specifique|electrique|mecanique|hydraulique|preciser)\b"
        ),
        "replacement": "",
        "severity": "warning",
        "message": "Accent manquant — version accentuée proposée.",
        "enabled": True,
    },
]


def seed_default_rules(db: Session) -> int:
    """Insert default demo rules if the rules table is empty.

    Returns the number of rows inserted (0 if the table already had
    rules — seeding never overwrites user customisations).
    """
    existing = db.scalar(select(Rule).limit(1))
    if existing is not None:
        return 0
    for spec in _DEFAULTS:
        db.add(Rule(**spec))
    db.commit()
    logger.info("default_rules_seeded", count=len(_DEFAULTS))
    return len(_DEFAULTS)


def sync_user_standard(db: Session) -> int:
    """Create and refresh the file-backed local standard catalog.

    The published built-in catalogs remain database-owned after their Alembic
    migrations. This one catalog is intentionally sourced from
    ``standards/user_rules.py`` so local experiments can be edited and tested
    after a backend restart without a new migration for every rule change.
    """
    spec = user_rules.USER_STANDARD_SPEC
    code = user_rules.STANDARD_CODE
    standard = db.scalar(select(Standard).where(Standard.code == code))
    now = datetime.now(timezone.utc)
    if standard is None:
        standard = Standard(
            code=code,
            label=user_rules.STANDARD_LABEL,
            description=user_rules.STANDARD_DESCRIPTION,
            builtin=True,
        )
        db.add(standard)
        db.flush()

    changed = 0
    for label in user_rules.CATALOG:
        payload = json.dumps(
            serialize_builtin_version(spec, label),
            ensure_ascii=False,
        )
        version = db.scalar(
            select(StandardVersion).where(
                StandardVersion.standard_id == standard.id,
                StandardVersion.label == label,
            )
        )
        if version is None:
            db.add(
                StandardVersion(
                    standard_id=standard.id,
                    label=label,
                    builtin=True,
                    catalog_json=payload,
                )
            )
            changed += 1
        elif version.catalog_json != payload:
            version.catalog_json = payload
            version.updated_at = now
            changed += 1

    db.commit()
    if changed:
        logger.info("user_standard_synced", code=code, changed_versions=changed)
    return changed
