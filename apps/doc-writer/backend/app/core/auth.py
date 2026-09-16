"""Session verification and RBAC for doc-writer under the atexispocs portal SSO.

Le modele en un paragraphe : le compte Active Directory corporatif
s'authentifie (avec MFA) au niveau du PORTAL atexispocs, qui emet la cookie de
session PARTAGEE `atexispocs_session`. doc-writer ne fait PLUS de login : il
VERIFIE cette cookie (memes nom + secrets que le portal), revalide aupres du
service d'identite MS365 a chaque requete, puis AUTORISE contre sa PROPRE table
utilisateur/role (app.core.auth_db) et filtre les donnees par email. L'email
corporatif verifie est la cle de jointure ; l'appartenance a un groupe AD n'est
jamais lue pour decider d'un role.

`settings.auth_enabled` (defaut False) : require_authenticated/require_admin
exigent une session valide quand True ; renvoient None sans rien verifier quand
False (tier1 local inchange).

Cookie = base64(JSON payload) + "." + HMAC-SHA256(payload). Le
`verification_token` MS365 y est chiffre au repos via AESGCM. Le ROLE n'est PAS
dans la cookie (le portal ne connait pas les roles d'app) : il est relu dans
l'AUTHDB de doc-writer a chaque requete (`resolve_authenticated_user`). Les deux
secrets (HMAC + AESGCM) sont PARTAGES avec le portal via des fichiers communs
(cf. settings.session_hmac_secret_path / session_enc_key_path).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, cast

from fastapi import HTTPException, Request, status

from app.config import settings
from app.core.encryption import SecretManager, load_or_create_local_key

logger = logging.getLogger(__name__)

# Nom de la cookie PARTAGEE emise par le portal (contrat SSO).
SESSION_COOKIE_NAME = settings.session_cookie_name

# Roles internes — doivent correspondre a app.core.auth_db.VALID_ROLES.
ROLE_ADMIN = "admin"
ROLE_USER = "user"


@dataclass
class AuthenticatedUser:
    """Identite attachee a request.state.user une fois la session verifiee.

    `verification_token` est le jeton porteur MS365 en clair pour CETTE
    requete uniquement (dechiffre depuis la cookie) — ne jamais le logger ;
    utilise uniquement pour appeler ms365_identity_validate/_logout."""

    email: str
    display_name: str
    role: str
    verification_token: str
    roles: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.roles:
            self.roles = [self.role]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def auth_disabled_reason() -> Optional[str]:
    if not settings.auth_enabled:
        return "Authentification non activee (pilote MFA en attente d'activation)."
    return None


# --- Verification de la cookie PARTAGEE (emise par le portal) ----------------
# doc-writer NE CREE PLUS de cookie (le portal le fait apres le MFA). Il utilise
# les MEMES deux secrets partages pour VERIFIER : HMAC pour la signature, AESGCM
# pour dechiffrer le verification_token embarque. Format identique a
# apps/portal/backend/app/core/session.py (duplication de pilote, cf. §3 du
# checklist SSO).


def _hmac_secret() -> str:
    return load_or_create_local_key(Path(settings.session_hmac_secret_path))


def _enc_key() -> str:
    return load_or_create_local_key(Path(settings.session_enc_key_path))


def _sign(payload_b64: str) -> str:
    digest = hmac.new(_hmac_secret().encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_session_token(token: str) -> Optional[AuthenticatedUser]:
    """Verifie et decode la cookie partagee, ou None si invalide/expiree.

    Le ROLE n'est PAS dans la cookie (le portal ne le connait pas) -> role=""
    ici ; il est renseigne par l'AUTHDB dans `resolve_authenticated_user`.
    N'appelle PAS ms365_identity_validate (appel reseau async) — c'est le role
    de `resolve_authenticated_user` (AuthMiddleware)."""
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None

    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None

    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:  # noqa: BLE001
        return None

    if payload.get("exp", 0) < time.time():
        return None

    try:
        verification_token = SecretManager(_enc_key()).decrypt(payload["vt"])
        if not verification_token:
            return None
        return AuthenticatedUser(
            email=payload["email"],
            display_name=payload.get("display_name", ""),
            role="",  # inconnu depuis la cookie ; renseigne via l'AUTHDB.
            verification_token=verification_token,
        )
    except (KeyError, TypeError):
        return None


# --- Dependances FastAPI -----------------------------------------------------


def require_authenticated(request: Request) -> Optional[AuthenticatedUser]:
    """Exige une session valide. No-op (renvoie None) tant que
    `auth_enabled=False` — toute route utilisant cette dependance se comporte
    exactement comme avant le pilote MFA.

    `request.state.user` est peuple par app/main.py's AuthMiddleware, qui a
    deja (a) verifie la cookie de session signee et (b) appele
    ms365_identity_validate + relu la fiche AUTHDB pour cette requete."""
    if not settings.auth_enabled:
        return None
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return cast(AuthenticatedUser, user)


async def resolve_authenticated_user(session_cookie_value: str) -> Optional[AuthenticatedUser]:
    """Resolution complete par requete, utilisee par AuthMiddleware :

      1. Verifier la cookie de session signee (prouve qu'elle a ete emise par
         ce serveur apres une connexion MCP reussie) et dechiffrer le
         verification_token MS365 embarque.
      2. Appeler ms365_identity_validate sur ce jeton — rejeter sauf si
         `valid` ET `mfa_verified` sont tous deux vrais. JAMAIS mis en cache.
      3. Relire la fiche AUTHDB pour l'email (lookup cote serveur, jamais se
         fier au role embarque dans la cookie seule) — rejeter si le compte
         n'existe plus ou a ete desactive depuis l'emission de la cookie.

    Renvoie None (ne leve jamais) sur tout echec — fail-closed."""
    base_user = verify_session_token(session_cookie_value)
    if base_user is None:
        return None

    from app.core import ms365_identity_client

    try:
        validation = await ms365_identity_client.validate(base_user.verification_token)
    except ms365_identity_client.Ms365IdentityError as exc:
        logger.warning("Session revalidation failed (identity service): %s", exc)
        return None

    identity_user = validation.get("user") or {}
    if not validation.get("valid") or not identity_user.get("mfa_verified"):
        logger.warning("Session revalidation rejected: valid/mfa_verified not both true")
        return None

    validated_email = (identity_user.get("email") or "").strip().lower()
    if not validated_email or validated_email != base_user.email:
        logger.warning("Session revalidation rejected: email mismatch between cookie and identity service")
        return None

    from app.core.auth_db import get_auth_db_service

    try:
        record = get_auth_db_service().get_user_by_email(validated_email)
    except Exception:  # noqa: BLE001
        logger.exception("AUTHDB lookup failed during session revalidation")
        return None

    if record is None or not record.is_active:
        return None

    return AuthenticatedUser(
        email=record.email,
        display_name=record.display_name,
        role=record.role,
        verification_token=base_user.verification_token,
    )


def require_admin(request: Request) -> Optional[AuthenticatedUser]:
    """Exige une session valide avec le role admin. No-op tant que
    `auth_enabled=False`."""
    if not settings.auth_enabled:
        return None
    user = require_authenticated(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if not user.has_role(ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
