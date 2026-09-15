"""Routes /api/v1/auth — connexion MCP-deleguee (MFA pilot, R1).

Implemente le flux de bout en bout :
  POST /api/v1/auth/start        -> ms365_identity_start (email seul, pas de mdp)
  WS   /api/v1/auth/ws/{auth_id} -> proxy reverse same-origin vers le WebSocket
                                     MFA du service d'identite (le navigateur
                                     ne parle jamais directement a 172.21.28.81)
  GET  /api/v1/auth/poll/{auth_id} -> ms365_identity_status, repli si le
                                     WebSocket tombe avant auth_complete
  GET  /api/v1/auth/session      -> etat de session courant pour la SPA
  POST /api/v1/auth/logout       -> ms365_identity_logout + efface la cookie
  GET  /api/v1/auth/me           -> utilisateur authentifie courant

  Admin (require_admin) :
  GET  /api/v1/auth/users            -> liste AUTHDB
  POST /api/v1/auth/users            -> cree un utilisateur (email + role)
  PATCH /api/v1/auth/users/{email}   -> change le role
  POST /api/v1/auth/users/{email}/activate | /deactivate

Chaque endpoint degrade en "non active" tant que `settings.auth_enabled=False`
(interrupteur par defaut pour le dev local sans service d'identite joignable).

Pas de flux OIDC, pas d'enregistrement d'app Entra ID, pas de gestion locale
de mot de passe au-dela du seul relai decrit : la paire email+mot de passe
collectee par la SPA est envoyee UNIQUEMENT via le proxy WebSocket
(ms365_ws_proxy ci-dessous), directement au service d'identite en amont, et
n'est jamais loggee, stockee, ni vue par le reste de ce module.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.core import ms365_identity_client
from app.core.auth import (
    SESSION_COOKIE_NAME,
    AuthenticatedUser,
    auth_disabled_reason,
    require_admin,
    require_authenticated,
    verify_session_token,
)
from app.core.auth_db import (
    AuthDBUser,
    UserAlreadyExistsError,
    UserNotFoundError,
    get_auth_db_service,
)
from app.schemas import (
    AuthMeOut,
    AuthSessionOut,
    AuthUserIn,
    AuthUserOut,
)

logger = logging.getLogger("doc_writer.auth")

# SSO portal (option A) : le LOGIN (start/poll/ws/MFA) vit dans le portal
# atexispocs, pas ici. doc-writer n'expose que : lecture de session, /me,
# logout, et l'administration de SA table utilisateurs (require_admin). Il
# VERIFIE la cookie partagee emise par le portal (cf. app.core.auth).
router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(u: AuthDBUser) -> AuthUserOut:
    return AuthUserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
        updated_at=u.updated_at,
        last_login_at=u.last_login_at,
        added_by=u.added_by,
    )


@router.get("/session", response_model=AuthSessionOut)
async def get_session(request: Request) -> AuthSessionOut:
    reason = auth_disabled_reason()
    if reason:
        return AuthSessionOut(enabled=False, authenticated=False, disabled_reason=reason)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = verify_session_token(token) if token else None
    return AuthSessionOut(
        enabled=True,
        authenticated=user is not None,
        email=user.email if user else None,
        display_name=user.display_name if user else None,
        role=user.role if user else None,
    )


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = verify_session_token(token) if token else None
    if user is not None:
        try:
            await ms365_identity_client.logout(user.verification_token)
        except ms365_identity_client.Ms365IdentityError:
            logger.warning("ms365_identity_logout failed during sign-out; clearing local session anyway")

    response = JSONResponse(content={"status": "logged_out"})
    # Meme `path` que la cookie emise par le portal, sinon le navigateur ne la
    # fait pas correspondre et elle survivrait au logout. NB : logout est
    # global (cf. SSO option A) — la cookie partagee couvre tout /atexispocs/.
    response.delete_cookie(SESSION_COOKIE_NAME, path=settings.session_cookie_path)
    return response


@router.get("/me", response_model=AuthMeOut)
async def me(request: Request) -> AuthMeOut:
    user = require_authenticated(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=auth_disabled_reason())
    return AuthMeOut(email=user.email, display_name=user.display_name, role=user.role)


# ---------------------------------------------------------------------------
# Administration AUTHDB (require_admin)
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AuthUserOut])
def list_users(user: AuthenticatedUser | None = Depends(require_admin)) -> list[AuthUserOut]:
    return [_user_out(u) for u in get_auth_db_service().list_users()]


@router.post("/users", response_model=AuthUserOut)
def create_user(body: AuthUserIn, user: AuthenticatedUser | None = Depends(require_admin)) -> AuthUserOut:
    added_by = user.email if user else "system"
    try:
        created = get_auth_db_service().create_user(body.email, body.role, added_by)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _user_out(created)


@router.patch("/users/{email}", response_model=AuthUserOut)
def update_user_role(
    email: str, body: AuthUserIn, user: AuthenticatedUser | None = Depends(require_admin)
) -> AuthUserOut:
    try:
        updated = get_auth_db_service().update_role(email, body.role)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _user_out(updated)


@router.post("/users/{email}/activate", response_model=AuthUserOut)
def activate_user(email: str, user: AuthenticatedUser | None = Depends(require_admin)) -> AuthUserOut:
    try:
        updated = get_auth_db_service().set_active(email, True)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _user_out(updated)


@router.post("/users/{email}/deactivate", response_model=AuthUserOut)
def deactivate_user(email: str, user: AuthenticatedUser | None = Depends(require_admin)) -> AuthUserOut:
    try:
        updated = get_auth_db_service().set_active(email, False)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _user_out(updated)
