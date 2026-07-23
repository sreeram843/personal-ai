"""Encrypt/decrypt sensitive settings (provider API keys) with Fernet."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings


class SettingsCryptoError(RuntimeError):
    pass


def _fernet_key_from_secret(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _fernet_for_secret(secret: str) -> Fernet:
    return Fernet(_fernet_key_from_secret(secret))


def get_fernet(settings: Optional[Settings] = None) -> Fernet:
    cfg = settings or get_settings()
    secret = (cfg.settings_secret_key or "").strip() or cfg.jwt_secret
    if not secret or secret == "dev-change-me-in-production":
        # Still allow local/dev with jwt_secret; warn via dedicated key in prod docs.
        secret = cfg.jwt_secret
    return _fernet_for_secret(secret)


def encrypt_secret(plaintext: str, settings: Optional[Settings] = None) -> str:
    token = get_fernet(settings).encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str, settings: Optional[Settings] = None) -> str:
    try:
        return get_fernet(settings).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SettingsCryptoError("Unable to decrypt secret; check SETTINGS_SECRET_KEY") from exc


def key_last4(plaintext: str) -> str:
    text = plaintext.strip()
    if len(text) <= 4:
        return text
    return text[-4:]


__all__ = [
    "SettingsCryptoError",
    "decrypt_secret",
    "encrypt_secret",
    "get_fernet",
    "key_last4",
]
