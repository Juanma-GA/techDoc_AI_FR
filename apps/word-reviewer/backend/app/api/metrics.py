"""Route /api/v1/metrics - taux d'acceptation par regle (proxy de precision).

Consomme par l'onglet Donnees : une regle qui « crie au loup » (beaucoup de
rejets) se reconnait a un faible taux d'acceptation. Couche 4 de fiabilisation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Suggestion
from app.db.session import get_db
from app.schemas import MetricRuleOut, MetricsOut


router = APIRouter(prefix="/metrics", tags=["metrics"])

_ACCEPTED = {"accepted", "applied", "edited", "checked"}


@router.get("", response_model=MetricsOut)
def metrics(db: Session = Depends(get_db)) -> MetricsOut:
    rows = db.execute(
        select(Suggestion.rule_code, Suggestion.status, func.count(Suggestion.id)).group_by(
            Suggestion.rule_code, Suggestion.status
        )
    ).all()
    agg: dict[str, dict[str, int]] = {}
    for rule_code, status, count in rows:
        bucket = agg.setdefault(rule_code, {"accepted": 0, "rejected": 0, "total": 0})
        bucket["total"] += count
        if status in _ACCEPTED:
            bucket["accepted"] += count
        elif status == "rejected":
            bucket["rejected"] += count
    out: list[MetricRuleOut] = []
    for rule_code, b in sorted(agg.items()):
        decided = b["accepted"] + b["rejected"]
        rate = (b["accepted"] / decided) if decided else 0.0
        out.append(
            MetricRuleOut(
                rule_code=rule_code,
                total=b["total"],
                accepted=b["accepted"],
                rejected=b["rejected"],
                acceptance_rate=round(rate, 3),
            )
        )
    return MetricsOut(rules=out)
