from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from app.core.config import get_settings


class WhatsAppConfirmationError(ValueError):
    pass


def _secret() -> bytes:
    value = get_settings().integration_secret_master_key.encode("utf-8")
    return hashlib.sha256(b"whatsapp-confirmation:" + value).digest()


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise WhatsAppConfirmationError("Confirmação de envio inválida.") from exc


def create_whatsapp_confirmation(
    *,
    integration_public_id: str,
    to: str,
    text: str,
    ttl_seconds: int = 300,
) -> tuple[str, datetime]:
    expires = int(time.time()) + ttl_seconds
    payload = {
        "integration": integration_public_id,
        "to": to,
        "text": text,
        "exp": expires,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    signature = hmac.new(_secret(), raw, hashlib.sha256).digest()
    token = f"{_encode(raw)}.{_encode(signature)}"
    return token, datetime.fromtimestamp(expires, tz=timezone.utc)


def verify_whatsapp_confirmation(
    token: str,
    *,
    integration_public_id: str,
    to: str,
    text: str,
) -> None:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise WhatsAppConfirmationError("Confirmação de envio inválida.") from exc

    raw = _decode(payload_part)
    received_signature = _decode(signature_part)
    expected_signature = hmac.new(_secret(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(received_signature, expected_signature):
        raise WhatsAppConfirmationError("Confirmação de envio inválida.")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WhatsAppConfirmationError("Confirmação de envio inválida.") from exc

    if not isinstance(payload, dict):
        raise WhatsAppConfirmationError("Confirmação de envio inválida.")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise WhatsAppConfirmationError("A confirmação de envio expirou.")
    if (
        payload.get("integration") != integration_public_id
        or payload.get("to") != to
        or payload.get("text") != text
    ):
        raise WhatsAppConfirmationError(
            "A mensagem foi alterada depois da prévia. Gere uma nova confirmação."
        )
