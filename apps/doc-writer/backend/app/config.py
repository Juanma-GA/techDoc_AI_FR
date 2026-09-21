"""Application settings — loaded from env / .env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "doc-writer"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'doc-writer.db'}"
    storage_dir: str = str(BASE_DIR / "data" / "storage")

    # Tier mode : tier1 (local-only) vs tier2 (cloud + auth).
    # tier1 (default) : development, bind 127.0.0.1, no auth required.
    # tier2 : production/cloud, bind 0.0.0.0, auth middleware required.
    tier_mode: str = "tier1"

    # Hote de bind uvicorn. Palier 1 (local) : 127.0.0.1. L'IT le passe a une
    # valeur exposee au deploiement (palier 2/3) via .env — ce qui rend les
    # protections sensibles OBLIGATOIRES (cf. main._validate_security_posture).
    bind_host: str = "127.0.0.1"

    # Deploiement derriere un reverse-proxy (ex. nginx partage du workspace
    # is-team-dev-1-jjm) : uvicorn reste sur 127.0.0.1 (bind local) MAIS l'app
    # est joignable de l'exterieur via le proxy. Sans ce flag, F-02 croirait
    # a tort etre en local et laisserait passer un deploiement expose SANS
    # auth. A true, _validate_security_posture() applique la validation stricte
    # (auth pleinement configuree obligatoire) exactement comme un bind expose.
    exposed_behind_proxy: bool = False

    # NoDecode : sans lui, pydantic-settings tente un json.loads() sur la valeur
    # du .env pour les champs "complexes" (list/dict) AVANT les validators. Une
    # liste CSV (ex. "https://host,https://host2") n'est pas du JSON -> crash au
    # demarrage. NoDecode desactive ce decode et laisse le validator ci-dessous
    # parser le CSV. Meme correctif que corpus-agent.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
    ]
    max_upload_size_mb: int = 50

    # Cle de chiffrement AES-256-GCM (base64, >=32 chars) pour la cle Mistral stockee
    # dans AppConfig. Vide en local (tier1) : une cle est alors auto-provisionnee
    # sur disque (cf. `encryption_key_path` / F-05, mistral_client._get_secret_manager)
    # -> le stockage en clair n'est plus le comportement par defaut. En prod, l'IT
    # fournit explicitement une cle via .env, generee avec
    # app.core.encryption.generate_key() (cf. .env.example).
    encryption_key: str = ""
    # Emplacement de la cle auto-provisionnee quand `encryption_key` est vide
    # (F-05). A cote de la DB par defaut (deja gitignore, cf. `database_url`).
    encryption_key_path: str = str(BASE_DIR / "data" / ".encryption_key")

    mistral_api_key: str = ""
    # Endpoint Mistral APPROUVE (doc politique 159 "Secure/Approved AI Tools") :
    # environnement enterprise dedie, pas l'API publique api.mistral.ai. Tout
    # changement de base_url (via Parametres) est verifie contre
    # `mistral_allowed_base_urls` (cf. mistral_client.save_settings) -> F-01.
    mistral_base_url: str = "https://api.2a91ec1812a1.dc.mistral.ai"
    # Allow-list des base_url autorisees pour le routage IA (F-01). CSV via
    # .env pour ajouter d'autres endpoints approuves ; NoDecode meme raison
    # que `cors_origins` ci-dessus (CSV, pas JSON).
    mistral_allowed_base_urls: Annotated[list[str], NoDecode] = [
        "https://api.2a91ec1812a1.dc.mistral.ai",
    ]
    mistral_chat_model: str = "mistral-small-latest"
    mistral_embed_model: str = "mistral-embed"
    # Lecture des PDF par Mistral (des qu'une cle API est configuree), en 3
    # niveaux de repli automatique :
    #   1. VISION (modele multimodal) : pages rendues en images et interpretees
    #      -> lit AUSSI le graphique (drapeaux, jauges/barres de niveau, etoiles)
    #      que l'OCR texte ne peut pas comprendre. Moteur par defaut.
    #   2. OCR document (/v1/ocr) : texte + structure (colonnes, tableaux).
    #   3. Extraction LOCALE (couche texte PyMuPDF + Tesseract).
    mistral_vision_model: str = "mistral-small-latest"
    mistral_ocr_model: str = "mistral-ocr-latest"
    # Transcription audio streamee via /v1/audio/transcriptions.
    # Voxtral Mini Transcribe 2 accepte les fichiers audio et `stream=true`.
    mistral_transcribe_model: str = "voxtral-mini-latest"
    # Cle API / endpoint DEDIES a la transcription Voxtral (optionnel). Permet
    # d'appeler Voxtral mini avec un compte/une cle differente de la cle Mistral
    # principale (ex. Voxtral active sur un abonnement a part). Vides = on retombe
    # sur `mistral_api_key` / `mistral_base_url` (comportement historique).
    voxtral_api_key: str = ""
    voxtral_base_url: str = ""

    # Repli LOCAL (quand Mistral indisponible) : couche texte PyMuPDF + OCR
    # Tesseract page par page sur les pages sans texte. Tesseract est un binaire
    # systeme externe (cf. README) ; absent -> page scannee vide, pas de crash.
    # `pdf_ocr_tessdata` pointe le dossier tessdata si TESSDATA_PREFIX absent.
    pdf_ocr_enabled: bool = True
    pdf_ocr_lang: str = "fra+eng"
    pdf_ocr_dpi: int = 300
    pdf_ocr_tessdata: str = ""

    # ---- MFA pilot (R1) : auth deleguee au service d'identite MS365 -----------
    # Palier 2 assume (ecart au standard local-first, cf. README ## Auth) :
    # active seulement si TOUT le bloc ci-dessous est configure ; sinon
    # _validate_security_posture() (main.py) continue de bloquer tout bind
    # non-local, exactement comme avant ce pilote (F-02).
    auth_enabled: bool = False

    # AUTHDB : Postgres DEDIE (separe de `database_url`), table email->role
    # propre a doc-writer. Ne stocke JAMAIS de mot de passe (l'AD/MFA se fait
    # entierement dans le service d'identite externe).
    authdb_host: str = ""
    authdb_port: int = 5432
    authdb_database: str = ""
    authdb_user: str = ""
    authdb_password: str = ""
    authdb_sslmode: str = "prefer"
    # §0 : email du premier admin AUTHDB, cree automatiquement au premier
    # demarrage si la table est vide (cf. auth_db.AuthDBService._seed_admin_if_empty)
    # -- sinon personne ne peut jamais appeler create_user (protege par
    # require_admin). Vide = pas de bootstrap (comportement par defaut).
    auth_seed_admin_email: str = ""

    # Service MCP d'identite MS365 corporatif deja deploye (meme cluster que
    # le scan-service / RAG politique, cf. hardening report).
    #
    # HTTP PLAIN par defaut (PAS https://172.21.28.81/mcp/ms365/mcp) : verifie
    # en direct (SSH dans is-team-dev-1-jjm) que KleamPy et elecgraph pointent
    # TOUS DEUX sur le backend interne en clair (elecgraph : config/auth.json
    # reel a "ms365_use_tls": false ; KleamPy : KLEAMPY_MS365_MCP_ENDPOINT=
    # http://127.0.0.1:3000/mcp/ms365/mcp, proxifie par le nginx partage du
    # workspace vers 172.21.28.81:8108 en clair). Le point HTTPS existe
    # (certificat CN=ai-gateway.local / issuer=AISM Internal CA valide,
    # confirme en direct) mais aucune des 3 apps de ce cluster (KleamPy,
    # elecgraph, IPMS via le meme chemin nginx) ne l'utilise en pratique ->
    # aucun CA bundle n'est jamais necessaire dans cet environnement.
    ms365_mcp_endpoint: str = "http://172.21.28.81:8108/mcp"
    # Bundle CA interne ("AISM Internal CA") pour le TLS vers l'endpoint
    # ci-dessus quand il est en https://. Vide -> https:// refuse au boot
    # (fail-closed, cf. _validate_auth_config) tant qu'il n'est pas fourni.
    ms365_ca_bundle: str = ""

    # --- Cookie de session PARTAGEE (SSO portal, option A) -------------------
    # doc-writer n'EMET plus la cookie : le PORTAL atexispocs la cree apres le
    # MFA. doc-writer la VERIFIE uniquement, avec les MEMES nom + secrets que
    # le portal (contrat SSO, cf. MFA_PORTAL_SSO_CHECKLIST_2026-09-14.md). Les
    # deux fichiers-secrets DOIVENT pointer sur les memes fichiers partages que
    # le portal en deploiement (via .env, ex. /home/coder/atexispocs/.session_*).
    session_cookie_name: str = "atexispocs_session"
    # Path que voit le navigateur (le routeur externe ne retire le prefixe que
    # cote nginx) : couvre TOUT le groupe atexispocs -> la cookie voyage vers
    # le portal ET chaque app.
    session_cookie_path: str = "/app/is-team-dev-1-jjm/atexispocs/"
    session_hmac_secret_path: str = str(BASE_DIR / "data" / ".session_hmac_key")
    session_enc_key_path: str = str(BASE_DIR / "data" / ".session_enc_key")
    auth_session_ttl_minutes: int = 720

    # §3 : email auquel rattacher les documents/sessions PRE-EXISTANTS lors de
    # la migration d'isolation par utilisateur (0003_user_scoping). Doit etre
    # fourni explicitement par l'operateur avant de lancer `alembic upgrade
    # head` sur une base ayant deja des donnees -- la migration refuse de
    # deviner (fail-closed) plutot que de laisser des lignes orphelines
    # invisibles a tout le monde une fois le filtrage par utilisateur actif.
    legacy_user_email: str = ""

    @field_validator("cors_origins", "mistral_allowed_base_urls", mode="before")
    @classmethod
    def _parse_csv_list(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def llm_configured(self) -> bool:
        return bool(self.mistral_api_key)

    @property
    def encryption_configured(self) -> bool:
        """Cle de chiffrement presente et assez longue pour AES-256-GCM."""
        return bool(self.encryption_key and len(self.encryption_key) >= 32)

    @property
    def auth_fully_configured(self) -> bool:
        """Tout le necessaire pour activer le pilote MFA (§2 F-02) : AUTHDB
        Postgres + endpoint d'identite + CA bundle si https://. Utilise par
        `main._validate_security_posture` pour decider si un bind non-local
        peut demarrer (auth reelle en place) ou doit rester bloque (F-02)."""
        if not self.auth_enabled:
            return False
        if not (self.authdb_host and self.authdb_database and self.authdb_user):
            return False
        if self.ms365_mcp_endpoint.startswith("https://") and not self.ms365_ca_bundle:
            return False
        return True


settings = Settings()
