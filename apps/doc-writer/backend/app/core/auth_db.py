"""AuthDB — table utilisateur/role DEDIEE de doc-writer (MFA pilot, R1).

Connexion PostgreSQL completement separee de `database_url` (qui reste SQLite
en tier1 pour les documents/sessions/messages). L'AUTHDB stocke exactement
une chose que cette app controle elle-meme : le mapping entre une adresse
email AD corporative (verifiee par le service MCP d'identite MS365 — cf.
app.core.ms365_identity_client) et un role doc-writer.

Contraintes de design (cf. MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md §1) :
  - AUCUNE colonne mot de passe/hash/salt/token de reset ici. L'AD authentifie
    (avec MFA) entierement hors de cette app ; cette table repond seulement a
    "cet email verifie a-t-il un compte doc-writer actif, et quel role".
  - L'email est stocke en minuscules et est la cle de jointure unique.
  - Les roles ne sont JAMAIS lus depuis l'appartenance a un groupe AD — ils
    vivent ici, geres uniquement via les endpoints admin.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

from app.config import settings

logger = logging.getLogger(__name__)

VALID_ROLES = ("admin", "user")


def normalize_email(email: str) -> str:
    """Trim + minuscules — la regle de normalisation qui fait de l'email la
    cle de jointure fiable ("casse mixte et espaces resolvent au meme user")."""
    return (email or "").strip().lower()


@dataclass
class AuthDBUser:
    """Une ligne de la table docwriter_users."""

    id: int
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    added_by: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "AuthDBUser":
        return cls(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_login_at=row["last_login_at"],
            added_by=row["added_by"],
        )


class UserAlreadyExistsError(Exception):
    """Leve par create_user() quand l'email (normalise) a deja une ligne AUTHDB."""


class UserNotFoundError(Exception):
    """Leve par update/activate/deactivate quand l'email (normalise) n'a aucune ligne AUTHDB."""


class AuthDBService:
    """Singleton proprietaire de la connexion AUTHDB.

    `initialize()` doit etre appelee une fois au demarrage (main.py lifespan)
    — ouvre la connexion et lance la migration idempotente. Posture
    fail-closed requise : une erreur de connexion ici doit interrompre le
    demarrage de l'app, jamais degrader silencieusement vers "continue sans
    auth" (il n'existe pas d'equivalent de repli sur ChromaDB pour
    l'autorisation)."""

    _instance: Optional["AuthDBService"] = None
    _conn: Optional["psycopg.Connection"] = None
    _initialized: bool = False
    _lock: threading.Lock

    def __new__(cls) -> "AuthDBService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._conn = None
            cls._instance._initialized = False
            cls._instance._lock = threading.Lock()
        return cls._instance

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _connect(self) -> "psycopg.Connection":
        """Connexion avec parametres separes (jamais une conninfo string
        construite a la main, pour que le mot de passe ne transite jamais
        dans une chaine qui pourrait etre renvoyee dans une erreur libpq)."""
        return psycopg.connect(
            host=settings.authdb_host,
            port=settings.authdb_port,
            dbname=settings.authdb_database,
            user=settings.authdb_user,
            password=settings.authdb_password or "",
            sslmode=settings.authdb_sslmode,
            connect_timeout=5,
            row_factory=dict_row,
            autocommit=True,
        )

    def initialize(self) -> None:
        """Connecte et lance la migration idempotente. Leve sur tout echec —
        les appelants (main.py lifespan) doivent laisser cela interrompre le
        demarrage plutot que catch-and-continue."""
        if self._initialized:
            logger.debug("AuthDB deja initialisee")
            return

        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS docwriter_users (
                    id             BIGSERIAL PRIMARY KEY,
                    email          TEXT NOT NULL UNIQUE,
                    display_name   TEXT NOT NULL DEFAULT '',
                    role           TEXT NOT NULL,
                    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                    last_login_at  TIMESTAMPTZ,
                    added_by       TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS docwriter_users_email_lower_idx "
                "ON docwriter_users (lower(email))"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS docwriter_users_role_idx ON docwriter_users (role)"
            )
            self._seed_admin_if_empty(conn)
            self._conn = conn
            self._initialized = True
            logger.info("AuthDB initialisee (table docwriter_users prete)")
        except Exception:
            conn.close()
            raise

    def _seed_admin_if_empty(self, conn: "psycopg.Connection") -> None:
        """Bootstrap (§0) : sans ceci, `docwriter_users` demarre vide et
        `create_user` (protege par `require_admin`) ne peut jamais etre
        appele -- personne ne peut jamais devenir le premier admin. Si la
        table est vide ET `settings.auth_seed_admin_email` est configure, ce
        compte est cree comme premier admin, UNE SEULE FOIS (ne fait plus
        rien des que la table a au moins une ligne, meme apres un redemarrage
        avec le meme email en config)."""
        seed = normalize_email(settings.auth_seed_admin_email)
        if not seed:
            return
        count = conn.execute("SELECT COUNT(*) AS n FROM docwriter_users").fetchone()["n"]
        if count > 0:
            return
        conn.execute(
            """
            INSERT INTO docwriter_users (email, display_name, role, is_active, added_by)
            VALUES (%s, '', 'admin', TRUE, 'bootstrap')
            ON CONFLICT (email) DO NOTHING
            """,
            (seed,),
        )
        logger.info("AuthDB bootstrap: seeded first admin %s", seed)

    def _execute(self, sql: str, params: Optional[Any] = None) -> Any:
        """Serialise toutes les requetes sous un lock — les connexions
        psycopg3 ne sont pas thread-safe pour un usage concurrent depuis le
        threadpool de FastAPI."""
        with self._lock:
            if self._conn is None:
                raise RuntimeError("AuthDB non initialisee")
            return self._conn.execute(sql, params)

    # ------------------------------------------------------------------
    # Lectures
    # ------------------------------------------------------------------

    def get_user_by_email(self, email: str) -> Optional[AuthDBUser]:
        normalized = normalize_email(email)
        row = self._execute(
            "SELECT * FROM docwriter_users WHERE email = %s", (normalized,)
        ).fetchone()
        return AuthDBUser.from_row(row) if row else None

    def list_users(self) -> list[AuthDBUser]:
        rows = self._execute(
            "SELECT * FROM docwriter_users ORDER BY created_at DESC"
        ).fetchall()
        return [AuthDBUser.from_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Ecritures gerees par un admin
    # ------------------------------------------------------------------

    def create_user(self, email: str, role: str, added_by: str) -> AuthDBUser:
        """Ajoute un utilisateur par email corporatif + role, avant meme sa
        premiere connexion. Pas de mot de passe, pas de credential
        d'invitation — juste la cle de jointure et le role accorde."""
        normalized = normalize_email(email)
        if role not in VALID_ROLES:
            raise ValueError(f"Role inconnu {role!r} ; doit etre l'un de {VALID_ROLES}")
        if self.get_user_by_email(normalized) is not None:
            raise UserAlreadyExistsError(f"Un utilisateur existe deja pour {normalized}")
        row = self._execute(
            """
            INSERT INTO docwriter_users (email, display_name, role, is_active, added_by)
            VALUES (%s, %s, %s, TRUE, %s)
            RETURNING *
            """,
            (normalized, "", role, normalize_email(added_by)),
        ).fetchone()
        return AuthDBUser.from_row(row)

    def update_role(self, email: str, role: str) -> AuthDBUser:
        normalized = normalize_email(email)
        if role not in VALID_ROLES:
            raise ValueError(f"Role inconnu {role!r} ; doit etre l'un de {VALID_ROLES}")
        row = self._execute(
            """
            UPDATE docwriter_users SET role = %s, updated_at = now()
            WHERE email = %s
            RETURNING *
            """,
            (role, normalized),
        ).fetchone()
        if row is None:
            raise UserNotFoundError(f"Aucun utilisateur trouve pour {normalized}")
        return AuthDBUser.from_row(row)

    def set_active(self, email: str, is_active: bool) -> AuthDBUser:
        """Desactive/reactive un utilisateur — independant de l'AD. Prend
        effet immediatement (AuthMiddleware relit cette fiche a chaque
        requete, jamais de cache)."""
        normalized = normalize_email(email)
        row = self._execute(
            """
            UPDATE docwriter_users SET is_active = %s, updated_at = now()
            WHERE email = %s
            RETURNING *
            """,
            (is_active, normalized),
        ).fetchone()
        if row is None:
            raise UserNotFoundError(f"Aucun utilisateur trouve pour {normalized}")
        return AuthDBUser.from_row(row)

    # ------------------------------------------------------------------
    # Mises a jour au moment de la connexion
    # ------------------------------------------------------------------

    def record_login(self, email: str, display_name: str) -> AuthDBUser:
        """Rafraichit display_name et last_login_at pour une connexion
        reussie. Appelee seulement apres que l'appelant a deja confirme que
        l'utilisateur existe et est actif ; ne change ni is_active ni role."""
        normalized = normalize_email(email)
        row = self._execute(
            """
            UPDATE docwriter_users
            SET display_name = %s, last_login_at = %s, updated_at = now()
            WHERE email = %s
            RETURNING *
            """,
            (display_name, datetime.now(timezone.utc), normalized),
        ).fetchone()
        if row is None:
            raise UserNotFoundError(f"Aucun utilisateur trouve pour {normalized}")
        return AuthDBUser.from_row(row)

    def get_status(self) -> str:
        return "healthy" if self._initialized else "not_initialized"


def get_auth_db_service() -> AuthDBService:
    """Recupere l'instance singleton du service AuthDB."""
    return AuthDBService()
