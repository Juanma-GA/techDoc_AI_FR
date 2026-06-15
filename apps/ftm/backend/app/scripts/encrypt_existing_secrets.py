"""Script de migración manual para cifrar secrets existentes en app_config.

IMPORTANTE: Este script debe ejecutarse DESPUÉS de configurar ENCRYPTION_KEY en .env

Uso:
    python -m app.scripts.encrypt_existing_secrets
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select

from app.config import settings
from app.core.encryption import SecretManager, EncryptionError
from app.core.mistral_client import ENCRYPTED_KEYS
from app.db.models import AppConfig
from app.db.session import SessionLocal


def main():
    """Encrypt existing plaintext secrets in database."""
    
    if not settings.encryption_key:
        print("ERROR: ENCRYPTION_KEY not configured in .env")
        print("Generate a key with:")
        print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        print("\nThen add to .env:")
        print("  ENCRYPTION_KEY=<generated_key>")
        return 1
    
    print(f"Encryption configured: {settings.encryption_configured}")
    print(f"Keys to encrypt: {ENCRYPTED_KEYS}")
    print()
    
    manager = SecretManager(settings.encryption_key)
    db = SessionLocal()
    
    try:
        # Find all secrets that need encryption
        for key in ENCRYPTED_KEYS:
            row = db.get(AppConfig, key)
            if not row or not row.value:
                print(f"[skip] {key}: not set")
                continue
            
            current_value = row.value
            
            # Check if already encrypted (Fernet tokens start with gAAAAA...)
            if current_value.startswith("gAAAAA"):
                print(f"[skip] {key}: already encrypted")
                continue
            
            # Encrypt the plaintext value
            try:
                encrypted = manager.encrypt(current_value)
                row.value = encrypted
                print(f"[encrypted] {key}: {current_value[:10]}... -> {encrypted[:20]}...")
            except EncryptionError as e:
                print(f"[error] {key}: {e}")
                return 1
        
        # Commit all changes
        db.commit()
        print("\n✓ All secrets encrypted successfully")
        return 0
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
