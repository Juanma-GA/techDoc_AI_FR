"""Routes /api/v1/users — local accounts (per-workstation profiles, no SSO).

Replaces the former browser-localStorage account store: emails and password
hashes now live only in the backend's SQLite database, never in client-side
storage. There is no session/cookie layer — the frontend keeps only the
non-sensitive "currently selected user id" locally and re-fetches the user
list on load.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.passwords import hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas import UserLoginIn, UserOut, UserRegisterIn, UserUpdateIn

log = logging.getLogger("xml_proofreader.users")

router = APIRouter(prefix="/users", tags=["users"])


def _out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, created_at=user.created_at)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [_out(u) for u in users]


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegisterIn, db: Session = Depends(get_db)) -> UserOut:
    norm = _normalize_email(payload.email)
    existing = db.scalar(select(User).where(User.email == norm))
    if existing is not None:
        raise AppError("EMAIL_EXISTS", "An account with this email already exists", status_code=409)

    salt_hex, hash_hex = hash_password(payload.password)
    user = User(
        name=payload.name.strip(),
        email=norm,
        password_salt=salt_hex,
        password_hash=hash_hex,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("user registered", extra={"user_id": user.id})
    return _out(user)


@router.post("/login", response_model=UserOut)
def login(payload: UserLoginIn, db: Session = Depends(get_db)) -> UserOut:
    norm = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == norm))
    if user is None or not verify_password(payload.password, user.password_salt, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password", status_code=401)
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_profile(user_id: str, payload: UserUpdateIn, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "User not found", status_code=404)

    norm = _normalize_email(payload.email)
    other = db.scalar(select(User).where(User.email == norm, User.id != user_id))
    if other is not None:
        raise AppError("EMAIL_EXISTS", "An account with this email already exists", status_code=409)

    user.name = payload.name.strip()
    user.email = norm
    db.commit()
    db.refresh(user)
    return _out(user)
