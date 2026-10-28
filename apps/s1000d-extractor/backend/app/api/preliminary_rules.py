"""Local settings for deterministic preliminary-requirement proposals."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.preliminary_rules import RulesConfig, RulesUpdate, read_rules, write_rules
from app.db.session import get_db

router = APIRouter(prefix="/settings/preliminary-rules", tags=["settings"])


@router.get("", response_model=RulesConfig)
def read(db: Session = Depends(get_db)) -> RulesConfig:
    return read_rules(db)


@router.post("", response_model=RulesConfig)
def write(payload: RulesUpdate, db: Session = Depends(get_db)) -> RulesConfig:
    return write_rules(db, payload)
