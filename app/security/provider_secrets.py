from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class ProviderSecretError(ValueError):
    pass


def _fernet() -> Fernet:
    passphrase = get_settings().integration_secret_master_key.encode("utf-8")
    digest = hashlib.sha256(passphrase).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_provider_secret(payload: dict[str, str]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return _fernet().encrypt(serialized.encode("utf-8")).decode("ascii")


def decrypt_provider_secret(value: str) -> dict[str, str]:
    try:
        raw = _fernet().decrypt(value.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderSecretError(
            "Não foi possível descriptografar a credencial da integração."
        ) from exc
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in payload.items()
    ):
        raise ProviderSecretError("Formato interno de credencial inválido.")
    return payload
