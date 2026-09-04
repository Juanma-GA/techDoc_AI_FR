"""app.core.passwords — PBKDF2 hashing used by /api/v1/users."""

from __future__ import annotations

from app.core.passwords import hash_password, verify_password


def test_hash_then_verify_correct_password() -> None:
    salt_hex, hash_hex = hash_password("S3cret!")
    assert len(salt_hex) == 32  # 16 bytes hex-encoded
    assert len(hash_hex) == 64  # sha256 digest hex-encoded
    assert verify_password("S3cret!", salt_hex, hash_hex) is True


def test_verify_rejects_wrong_password() -> None:
    salt_hex, hash_hex = hash_password("S3cret!")
    assert verify_password("wrong", salt_hex, hash_hex) is False


def test_hash_uses_random_salt_distinct_across_calls() -> None:
    salt_a, hash_a = hash_password("same")
    salt_b, hash_b = hash_password("same")
    assert salt_a != salt_b
    assert hash_a != hash_b
