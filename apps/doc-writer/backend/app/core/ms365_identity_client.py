"""Client for the already-deployed MS365 identity MCP service (MFA pilot, R1).

Calls the four `ms365_identity_*` MCP tools that perform corporate Microsoft
365 login + MFA server-side and hand back a verified identity. Does NOT
implement OIDC, SAML, OAuth, or any Microsoft-login automation of its own —
every credential/MFA interaction happens inside the identity service; this
module only speaks MCP "Streamable HTTP" JSON-RPC to it.

Ported from KleamPy's app/services/ms365_identity_client.py (same corporate
identity service, same 172.21.28.81 cluster) — see
MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md for the pilot's scope.

TLS: the identity service presents an internal cluster CA ("AISM Internal
CA") when reached over https:// — not a publicly-trusted certificate. Every
call here builds an `ssl.SSLContext` that trusts ONLY that CA bundle
(`settings.ms365_ca_bundle`); `verify=False` is never used. The plain-HTTP
internal backend port is a documented, supported alternative that needs no
CA at all (see `ms365_endpoint_uses_tls`).

Never logs `password`, `verification_token`, MFA codes, or full phone
numbers — only tool name / coarse status are logged.
"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import settings

logger = logging.getLogger(__name__)

_TOOL_START = "ms365_identity_start"
_TOOL_STATUS = "ms365_identity_status"
_TOOL_VALIDATE = "ms365_identity_validate"
_TOOL_LOGOUT = "ms365_identity_logout"

# Server-to-server calls to the identity MCP are short JSON-RPC round trips —
# bounded so a stalled upstream never hangs a request indefinitely (every
# protected request calls ms365_identity_validate).
_CALL_TIMEOUT_SECONDS = 15.0


class Ms365IdentityError(RuntimeError):
    """Raised when a call to the MS365 identity MCP service fails or returns
    a malformed/error result. Callers must treat this as "cannot verify
    identity right now" and fail closed (deny access), never fail open."""


_ssl_context: Optional[ssl.SSLContext] = None


def build_ms365_ssl_context() -> ssl.SSLContext:
    """Build (and cache) the ssl.SSLContext trusting the AISM Internal CA.

    Fails closed: `settings.auth_fully_configured` is checked at startup
    (main._validate_security_posture) before any non-local bind is allowed,
    so a missing bundle here means this function should never have been
    called for an https:// endpoint — raising is correct, not a silent
    fallback to the system trust store (which does not include the internal
    CA and would either fail every call, or worse, trust an unrelated but
    publicly-trusted impostor cert).
    """
    global _ssl_context
    if _ssl_context is not None:
        return _ssl_context

    ca_bundle = settings.ms365_ca_bundle
    if not ca_bundle:
        raise Ms365IdentityError(
            "ms365_ca_bundle n'est pas configure - impossible d'etablir une "
            "connexion TLS de confiance vers le service d'identite MS365"
        )
    context = ssl.create_default_context(cafile=ca_bundle)
    _ssl_context = context
    return context


def ms365_endpoint_uses_tls() -> bool:
    """True when `settings.ms365_mcp_endpoint` is configured for https://.

    The identity service exposes two equivalent transports on the same
    internal cluster network: an HTTPS gateway (presenting the AISM Internal
    CA, requires `ms365_ca_bundle`) and a plain-HTTP backend port on the same
    trusted network with no certificate involved. Choosing http:// is a
    legitimate, supported mode (mirrored from KleamPy) — not a verification
    bypass: when https:// IS selected, TLS is still always verified against
    the pinned CA (build_ms365_ssl_context).
    """
    return urlparse(settings.ms365_mcp_endpoint).scheme == "https"


def ms365_ws_base_url() -> str:
    """Build the ws(s):// base URL for the identity verification WebSocket
    (`/mcp/ms365/identity/verify/auth/{auth_id}`), derived from the same
    host *and scheme* configured for the JSON-RPC endpoint — the identity
    service's JSON-RPC and WebSocket endpoints live on the same host, over
    the same transport, by contract."""
    parsed = urlparse(settings.ms365_mcp_endpoint)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/mcp/ms365/identity/verify/auth"


def _first_text(raw: dict[str, Any]) -> Optional[str]:
    for item in raw.get("content", []):
        if item.get("type") == "text":
            return item.get("text")
    return None


def _extract_result(raw: dict[str, Any], tool_name: str) -> dict[str, Any]:
    if raw.get("isError"):
        text = _first_text(raw)
        raise Ms365IdentityError(f"{tool_name} a renvoye une erreur : {text or 'erreur inconnue'}")
    text = _first_text(raw)
    if text is None:
        raise Ms365IdentityError(f"{tool_name} n'a renvoye aucun contenu")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Ms365IdentityError(f"{tool_name} a renvoye du contenu non-JSON") from exc
    if not isinstance(parsed, dict):
        raise Ms365IdentityError(f"{tool_name} a renvoye un JSON qui n'est pas un objet")
    return parsed


async def _call_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Open a short-lived Streamable HTTP MCP session against the identity
    service and call one tool. Each call opens its own connection (quick
    JSON-RPC round trips) so concurrent sign-in/validate calls from
    different requests never contend on a shared session."""
    endpoint = settings.ms365_mcp_endpoint
    try:
        verify: Any = build_ms365_ssl_context() if ms365_endpoint_uses_tls() else True
        async with httpx.AsyncClient(
            verify=verify,
            timeout=httpx.Timeout(_CALL_TIMEOUT_SECONDS),
            # Internal cluster address (172.21.28.81) — the corporate Zscaler
            # egress proxy is only for outbound-to-internet traffic and must
            # never be consulted for this call.
            trust_env=False,
        ) as http_client:
            # mcp==2.2.0's streamable_http_client yields (read, write) only --
            # a 2-tuple, unlike the 3-tuple (+ get_session_id callable) that
            # KleamPy's reference implementation expects from its pinned
            # mcp==1.30.0. Found live (2026-09-14) via a real call against the
            # identity service : mcp 1.30.0 wasn't resolvable against this
            # project's other pins so 2.2.0 was installed instead (see
            # MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md §1) ; only importing
            # the symbols was checked at the time, not the runtime shape.
            async with streamable_http_client(endpoint, http_client=http_client) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, args)
                    raw = {
                        "content": [
                            {"type": c.type, "text": getattr(c, "text", None)} for c in result.content
                        ],
                        "isError": getattr(result, "isError", False),
                    }
                    return _extract_result(raw, tool_name)
    except Ms365IdentityError:
        raise
    except Exception as exc:  # noqa: BLE001
        # Never let the exception message leak `args` (may contain a
        # verification_token, or for `start`, an email — email is fine,
        # tokens are not) — log only the tool name and error type.
        logger.error("MS365 identity MCP call failed: tool=%s error=%s", tool_name, type(exc).__name__)
        raise Ms365IdentityError(
            f"Impossible de joindre le service d'identite MS365 ({tool_name})"
        ) from exc


# ---------------------------------------------------------------------------
# Public API — the four ms365_identity_* tools
# ---------------------------------------------------------------------------


async def start(email: str) -> dict[str, Any]:
    """ms365_identity_start {email} -> {auth_id, login_page_url?}

    Begins corporate AD sign-in for `email`. Does not touch the password —
    that is only ever sent over the WebSocket proxy (api/routes/auth.py),
    never through this JSON-RPC call."""
    logger.info("ms365_identity_start requested")
    return await _call_tool(_TOOL_START, {"email": email})


async def status(auth_id: str) -> dict[str, Any]:
    """ms365_identity_status {auth_id} -> pending | complete (+verification_token, user) | expired | failed"""
    return await _call_tool(_TOOL_STATUS, {"auth_id": auth_id})


async def validate(verification_token: str) -> dict[str, Any]:
    """ms365_identity_validate {verification_token} -> {valid, user:{email, name, mfa_verified, tenant_id}}

    Called on every protected request (AuthMiddleware) — never cached: this
    is the "MFA still verified, right now" guarantee."""
    return await _call_tool(_TOOL_VALIDATE, {"verification_token": verification_token})


async def logout(verification_token: str) -> dict[str, Any]:
    """ms365_identity_logout {verification_token} -> revokes the token immediately."""
    return await _call_tool(_TOOL_LOGOUT, {"verification_token": verification_token})
