"""Portal auth backend settings (MFA portal SSO, option A).

The portal owns the single MFA login for the whole atexispocs group and issues
the shared `atexispocs_session` cookie. Each app then VERIFIES that cookie with
the SAME two secrets (HMAC signing + AESGCM key), so the signing/encryption
material lives at SHARED paths that every backend reads — that's what makes one
login work across all apps (cf. MFA_PORTAL_SSO_CHECKLIST_2026-09-14.md).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "atexispocs-portal"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    bind_host: str = "127.0.0.1"

    # Origines CORS autorisees. En pratique le portal et les apps sont servis
    # sous la meme origine (via nginx), donc credentials same-origin ; liste
    # restreinte quand meme.
    cors_origins: list[str] = ["http://127.0.0.1:8005", "http://localhost:8005"]

    # --- Service MCP d'identite MS365 (meme que les apps ; HTTP plain interne,
    #     cf. recon 2026-09-14). Consomme par core/ms365_identity_client.py. ---
    ms365_mcp_endpoint: str = "http://172.21.28.81:8108/mcp"
    ms365_ca_bundle: str = ""
    # WebSocket du relais MFA interactif. VIDE par defaut -> derive au mieux
    # depuis ms365_mcp_endpoint (repli, casse en pratique : voir le bug 2026-09-15
    # ci-dessous). DOIT etre fourni explicitement en deploiement.
    #
    # Bug trouve en live (2026-09-15) : contacter directement le backend brut
    # ws://172.21.28.81:8108/mcp/ms365/identity/verify/auth/{id} echoue
    # (`InvalidMessage`) - ce chemin `/mcp/ms365/...` n'existe QUE derriere le
    # nginx partage du workspace, qui le reecrit et strip le prefixe avant de
    # forwarder en clair vers 172.21.28.81:8108 (cf.
    # /etc/nginx/sites-enabled/ipms-clone, location `/mcp/ms365/`, avec les
    # headers Upgrade/Connection necessaires au WS). KleamPy et elecgraph
    # passent TOUS DEUX par ce nginx local (127.0.0.1:3000) pour le relais MFA
    # (elecgraph : config/auth.json -> ms365_host=127.0.0.1, ms365_port=3000,
    # ms365_use_tls=false ; KleamPy : KLEAMPY_MS365_MCP_ENDPOINT=
    # http://127.0.0.1:3000/mcp/ms365/mcp). Le portal DOIT faire pareil :
    # ws://127.0.0.1:3000/mcp/ms365/identity/verify/auth (via .env en
    # deploiement).
    ms365_ws_endpoint: str = ""

    # --- Cookie de session PARTAGEE (contrat SSO option A) --------------------
    # Meme nom + memes secrets dans le portal ET chaque app.
    session_cookie_name: str = "atexispocs_session"
    # Path que voit le navigateur (le routeur externe ne retire le prefixe que
    # cote nginx). Doit couvrir toutes les apps -> le prefixe atexispocs.
    session_cookie_path: str = "/app/is-team-dev-1-jjm/atexispocs/"
    session_ttl_minutes: int = 720

    # Secrets PARTAGES sur disque (auto-provisionnes une fois, puis relus).
    # DOIVENT pointer sur les MEMES fichiers pour le portal et pour chaque app
    # -> emplacement commun hors d'un seul module app. En local (dev) : sous le
    # repo ; en deploiement : /home/coder/atexispocs/.session_* (voir .env).
    session_hmac_secret_path: str = str(BASE_DIR / "data" / ".session_hmac_key")
    session_enc_key_path: str = str(BASE_DIR / "data" / ".session_enc_key")


settings = Settings()
