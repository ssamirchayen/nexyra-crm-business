from __future__ import annotations

import hashlib
import hmac
import secrets

_INTAKE_KEY_PREFIX = "nxy_int_"


def new_integration_intake_key() -> str:
    return f"{_INTAKE_KEY_PREFIX}{secrets.token_urlsafe(36)}"


def hash_integration_intake_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def integration_intake_key_prefix(value: str) -> str:
    visible = value[:18]
    return f"{visible}…"


def verify_integration_intake_key(raw_key: str, expected_hash: str) -> bool:
    candidate = hash_integration_intake_key(raw_key)
    return hmac.compare_digest(candidate, expected_hash)
