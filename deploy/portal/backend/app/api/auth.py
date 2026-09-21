"""Portal MFA login routes (SSO option A).

The portal is the single sign-in point for the atexispocs group. It runs the
MFA flow against the corporate MS365 identity service and, on success, issues
the shared `atexispocs_session` cookie for ANY MFA-verified corporate email.
It does NOT check an AUTHDB or roles — each app authorizes on its own once it
trusts the cookie.

  POST /api/auth/start        -> ms365_identity_start (email only)
  WS   /api/auth/ws/{auth_id} -> same-origin relay to the MFA challenge
  GET  /api/auth/poll/{auth_id} -> ms365_identity_status; on complete, issue cookie
  GET  /api/auth/session      -> current session state
  POST /api/auth/logout       -> ms365_identity_logout + clear cookie
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote

import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.core import ms365_identity_client
from app.core.session import create_session_token, verify_session_token

logger = logging.getLogger("portal.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Domaine corporatif impose (meme regle que KleamPy/elecgraph :
# ATEXIS_EMAIL_RE dans elecgraph/src/elecgraph/auth_config.py) — le service
# d'identite MS365 est reserve au personnel @atexis.com, jamais un domaine
# externe/personnel.
_EMAIL_RE = re.compile(r"^[^@\s]+@atexis\.com$")


class StartIn(BaseModel):
    email: str


class StartOut(BaseModel):
    auth_id: str
    login_page_url: str | None = None


class SessionOut(BaseModel):
    authenticated: bool
    email: str | None = None
    display_name: str | None = None


@router.get("/session", response_model=SessionOut)
async def get_session(request: Request) -> SessionOut:
    token = request.cookies.get(settings.session_cookie_name)
    ident = verify_session_token(token) if token else None
    return SessionOut(
        authenticated=ident is not None,
        email=ident.email if ident else None,
        display_name=ident.display_name if ident else None,
    )


@router.post("/start", response_model=StartOut)
async def start_sign_in(body: StartIn) -> StartOut:
    # strip + lower avant de comparer, meme normalisation que elecgraph
    # (normalize_email) -> "Ana.Catalan@Atexis.COM" est accepte comme
    # "ana.catalan@atexis.com".
    email = (body.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'adresse doit etre une adresse professionnelle @atexis.com",
        )
    try:
        result = await ms365_identity_client.start(email)
    except ms365_identity_client.Ms365IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    auth_id = result.get("auth_id")
    if not auth_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service d'identite n'a pas renvoye d'auth_id",
        )
    return StartOut(auth_id=auth_id, login_page_url=result.get("login_page_url"))


async def _finalize(verification_token: str) -> JSONResponse:
    """auth_complete -> validate MFA -> issue the shared session cookie.

    No AUTHDB here: any corporate email that passed MFA gets a portal session;
    each app decides separately whether that email may use it."""
    try:
        validation = await ms365_identity_client.validate(verification_token)
    except ms365_identity_client.Ms365IdentityError as exc:
        return JSONResponse(status_code=502, content={"status": "failed", "message": str(exc)})

    identity_user = validation.get("user") or {}
    if not validation.get("valid") or not identity_user.get("mfa_verified"):
        return JSONResponse(
            status_code=200,
            content={"status": "denied", "message": "MFA non completee. Reessaie."},
        )

    email = (identity_user.get("email") or "").strip().lower()
    if not email:
        return JSONResponse(
            status_code=502,
            content={"status": "failed", "message": "Le service d'identite n'a pas renvoye d'email verifie"},
        )
    display_name = identity_user.get("name", "") or ""

    token = create_session_token(email=email, display_name=display_name, verification_token=verification_token)
    response = JSONResponse(content={"status": "complete", "email": email, "display_name": display_name})
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=not settings.bind_host.strip().lower() in {"127.0.0.1", "localhost", "::1"},
        samesite="lax",
        path=settings.session_cookie_path,
        max_age=settings.session_ttl_minutes * 60,
    )
    logger.info("portal sign-in succeeded for %s", email)
    return response


@router.get("/poll/{auth_id}")
async def poll_sign_in(auth_id: str) -> JSONResponse:
    try:
        result = await ms365_identity_client.status(auth_id)
    except ms365_identity_client.Ms365IdentityError as exc:
        return JSONResponse(status_code=502, content={"status": "failed", "message": str(exc)})
    state = result.get("status")
    if state == "pending":
        return JSONResponse(content={"status": "pending"})
    if state == "expired":
        return JSONResponse(content={"status": "expired", "message": "La demande a expire. Reessaie."})
    if state == "failed":
        return JSONResponse(content={"status": "failed", "message": result.get("message") or "Echec."})
    if state == "complete":
        vt = result.get("verification_token")
        if not vt:
            return JSONResponse(
                status_code=502,
                content={"status": "failed", "message": "Pas de verification_token renvoye"},
            )
        return await _finalize(vt)
    return JSONResponse(status_code=502, content={"status": "failed", "message": f"Statut inconnu : {state!r}"})


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    token = request.cookies.get(settings.session_cookie_name)
    ident = verify_session_token(token) if token else None
    if ident is not None:
        try:
            await ms365_identity_client.logout(ident.verification_token)
        except ms365_identity_client.Ms365IdentityError:
            logger.warning("ms365_identity_logout failed during sign-out; clearing local cookie anyway")
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(settings.session_cookie_name, path=settings.session_cookie_path)
    return response


@router.websocket("/ws/{auth_id}")
async def ms365_ws_proxy(websocket: WebSocket, auth_id: str) -> None:
    """Same-origin relay to the identity service's MFA WebSocket. The browser
    never talks to the identity host directly. `email`/`password` come from the
    connection query string, forwarded upstream unchanged, never logged/stored."""
    email = websocket.query_params.get("email", "").strip().lower()
    password = websocket.query_params.get("password", "")
    if not email or not password or not _EMAIL_RE.match(email):
        await websocket.close(code=4400, reason="email and password are required")
        return

    await websocket.accept()
    upstream_url = (
        f"{ms365_identity_client.ms365_ws_base_url()}/{auth_id}"
        f"?email={quote(email)}&password={quote(password)}"
    )
    ssl_context = None
    if ms365_identity_client.ms365_endpoint_uses_tls():
        try:
            ssl_context = ms365_identity_client.build_ms365_ssl_context()
        except ms365_identity_client.Ms365IdentityError as exc:
            await websocket.send_json({"type": "auth_error", "message": str(exc)})
            await websocket.close(code=1011)
            return

    try:
        async with websockets.connect(upstream_url, ssl=ssl_context, proxy=None) as upstream:

            async def _b2u() -> None:
                try:
                    while True:
                        await upstream.send(await websocket.receive_text())
                except WebSocketDisconnect:
                    pass

            async def _u2b() -> None:
                async for message in upstream:
                    await websocket.send_text(message if isinstance(message, str) else message.decode("utf-8"))

            tasks = [asyncio.ensure_future(_b2u()), asyncio.ensure_future(_u2b())]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    if t.exception():
                        logger.warning("portal WS relay ended: %s", type(t.exception()).__name__)
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                        try:
                            await t
                        except (asyncio.CancelledError, Exception):
                            pass
    except Exception as exc:  # noqa: BLE001
        logger.error("portal WS proxy failed upstream: %s", type(exc).__name__)
        try:
            await websocket.send_json(
                {"type": "auth_error", "message": "Impossible de joindre le service d'identite."}
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
