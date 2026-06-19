"""Seed des standards builtin au premier boot.

Seed **uniquement** ATA100 (referentiel par defaut). **Aucune regle custom**
n'est seedee : la table `Rule` reste vide tant que l'utilisateur n'a pas importe
sa checklist Excel. Idempotent : un standard deja present n'est pas re-cree.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.checks.standards import BUILTIN_STANDARDS
from app.db.models import Standard, StandardVersion


def seed_builtin_standards(db: Session) -> int:
    """Insere les standards builtin manquants. Retourne le nb de standards crees."""
    created = 0
    for spec in BUILTIN_STANDARDS:
        code = str(spec["code"])
        existing = db.scalar(select(Standard).where(Standard.code == code))
        if existing is not None:
            continue
        standard = Standard(
            code=code,
            label=str(spec["label"]),
            description=str(spec.get("description") or ""),
            builtin=True,
        )
        db.add(standard)
        db.flush()
        versions = spec.get("versions") or {}
        for label, rules in versions.items():  # type: ignore[union-attr]
            catalog = [r.as_dict() for r in rules]
            db.add(
                StandardVersion(
                    standard_id=standard.id,
                    label=str(label),
                    builtin=True,
                    catalog_json=json.dumps(catalog, ensure_ascii=False),
                )
            )
        created += 1
    if created:
        db.commit()
    return created
