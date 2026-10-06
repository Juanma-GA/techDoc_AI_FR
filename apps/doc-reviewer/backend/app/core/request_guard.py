"""Garde HTTP « local-first » — protege l'API sans authentification.

Doc Reviewer tourne sur le poste de l'utilisateur (127.0.0.1) sans login. Sans
ce garde, n'importe quel site web visite par l'utilisateur pouvait piloter
l'API locale depuis son navigateur :

- **CSRF « drive-by »** : un formulaire multipart ou un `fetch` « simple »
  (sans pre-vol CORS) envoye vers http://127.0.0.1:8003 deposait un document,
  modifiait la config Mistral ou declenchait `/admin/reset`.
- **DNS rebinding** : un domaine attaquant re-resolu vers 127.0.0.1 devient
  « same-origin » pour le navigateur et peut LIRE les documents (export
  controle, documents client) — seul l'en-tete Host trahit l'attaque.

Defenses (aucune ne demande de login, le poste mono-utilisateur reste utilisable) :

1. **Host** : seuls les hotes de bouclage et `ALLOWED_HOSTS` sont acceptes.
2. **Methodes mutantes** (POST/PUT/PATCH/DELETE) : l'en-tete
   `X-Requested-With: doc-reviewer` est exige. Un en-tete personnalise rend la
   requete « non simple » : le navigateur doit faire un pre-vol CORS, refuse
   pour toute origine non autorisee. Le front l'envoie systematiquement.
3. **Origin** : si present sur une methode mutante, il doit etre la meme
   origine que le Host, ou figurer dans `CORS_ORIGINS`.
4. **Exposition** : une requete relayee par un proxy (en-tetes Forwarded /
   X-Forwarded-* / X-Real-IP) ou recue sur une adresse locale non-bouclage est
   refusee tant que l'IT n'a pas atteste un reverse proxy authentifiant
   (`BEHIND_AUTH_PROXY=true`). C'est la verification a l'execution qui manquait
   a `_validate_security_posture` : celle-ci se fie a BIND_HOST, alors que le
   bind reel est decide par la ligne de commande uvicorn.

Middleware ASGI pur (pas `BaseHTTPMiddleware`) : n'interfere pas avec le flux
SSE de `/analyze`.
"""

from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.core.logging import get_logger


CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_VALUE = "doc-reviewer"

_LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_FORWARDING_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-real-ip",
)

logger = get_logger(__name__)


def split_host_port(value: str) -> tuple[str, str | None]:
    """Decoupe un en-tete Host (`h`, `h:p`, `[::1]:p`) en (hote minuscule, port)."""
    raw = value.strip().lower()
    if raw.startswith("["):
        end = raw.find("]")
        if end < 0:
            return raw, None
        host = raw[1:end]
        rest = raw[end + 1:]
        return host, (rest[1:] if rest.startswith(":") and rest[1:] else None)
    if raw.count(":") == 1:
        host, port = raw.split(":", 1)
        return host, (port or None)
    return raw, None


def is_loopback_host(host: str) -> bool:
    return host in _LOOPBACK_HOSTNAMES


def host_allowed(host_header: str | None) -> bool:
    """Vrai si l'en-tete Host designe le poste local ou un hote de `ALLOWED_HOSTS`."""
    if not host_header:
        return False
    host, port = split_host_port(host_header)
    if not host:
        return False
    if is_loopback_host(host):
        return True
    for entry in settings.allowed_hosts:
        allowed_host, allowed_port = split_host_port(entry)
        if allowed_host != host:
            continue
        if allowed_port is None or allowed_port == port:
            return True
    return False


def _normalize_origin(value: str) -> str:
    return value.strip().rstrip("/").lower()


def origin_allowed(origin: str, host_header: str | None) -> bool:
    """Origin accepte : meme origine que le Host de la requete, ou `CORS_ORIGINS`."""
    normalized = _normalize_origin(origin)
    if not normalized or normalized == "null":
        return False
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return False
    if host_header and parts.netloc == host_header.strip().lower():
        return True
    return normalized in {_normalize_origin(o) for o in settings.cors_origins}


def is_proxied(headers: Headers) -> bool:
    return any(name in headers for name in _FORWARDING_HEADERS)


def server_address_is_exposed(scope: Scope) -> bool:
    """Vrai si la connexion est arrivee sur une adresse IP locale non-bouclage
    (ex. bind 0.0.0.0 joint via l'IP du poste ou du conteneur)."""
    server = scope.get("server")
    if not server:
        return False
    try:
        address = ipaddress.ip_address(str(server[0]))
    except ValueError:
        # Socket unix / client de test : pas d'adresse IP a evaluer.
        return False
    return not address.is_loopback


class RequestGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        method = scope.get("method", "GET").upper()
        host_header = headers.get("host")

        if not settings.behind_auth_proxy and (
            is_proxied(headers) or server_address_is_exposed(scope)
        ):
            await self._reject(
                scope, send, 403, "EXPOSURE_NOT_ALLOWED",
                "Acces distant refuse : cette instance n'a pas d'authentification. "
                "Elle n'est utilisable qu'en local (127.0.0.1), ou derriere un reverse "
                "proxy authentifiant atteste par l'IT (BEHIND_AUTH_PROXY=true).",
            )
            return

        if not host_allowed(host_header):
            await self._reject(
                scope, send, 400, "HOST_NOT_ALLOWED",
                "En-tete Host non autorise (protection anti DNS-rebinding).",
            )
            return

        if method not in _SAFE_METHODS:
            origin = headers.get("origin")
            if origin is not None and not origin_allowed(origin, host_header):
                await self._reject(
                    scope, send, 403, "ORIGIN_NOT_ALLOWED",
                    "Origine de la requete non autorisee.",
                )
                return
            if headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
                await self._reject(
                    scope, send, 403, "CSRF_HEADER_MISSING",
                    f"En-tete {CSRF_HEADER} requis pour les requetes de modification.",
                )
                return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, send: Send, status: int, code: str, message: str) -> None:
        logger.warning(
            "request_guard_rejected",
            code=code,
            method=scope.get("method"),
            path=scope.get("path"),
        )
        body = json.dumps(
            {"code": code, "message": message, "detail": None, "request_id": ""},
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
