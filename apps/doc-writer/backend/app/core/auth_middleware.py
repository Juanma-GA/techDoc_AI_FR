"""AuthMiddleware — peuple `request.state.user` pour chaque requete HTTP
(MFA pilot, R1).

No-op quand `settings.auth_enabled=False` (comportement tier1 inchange).
Quand actif : lit la cookie de session, la revalide en integralite via
`app.core.auth.resolve_authenticated_user` (signature + service d'identite
MS365 + fiche AUTHDB, jamais mis en cache), et pose `request.state.user` a
`AuthenticatedUser` ou `None`. Ne renvoie JAMAIS elle-meme un 401 — ce sont
les dependances `require_authenticated`/`require_admin` (app.core.auth) qui
decident route par route si l'absence de session est bloquante.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.core.auth import SESSION_COOKIE_NAME, resolve_authenticated_user


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request.state.user = None
        if settings.auth_enabled:
            token = request.cookies.get(SESSION_COOKIE_NAME)
            if token:
                request.state.user = await resolve_authenticated_user(token)
        return await call_next(request)
