from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import Settings

logger = logging.getLogger(__name__)


class PasswordResetDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class PasswordResetDeliveryResult:
    channel: str
    delivered: bool


def build_password_reset_url(base_url: str, token: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'token': token})}"


def _smtp_message(
    *,
    recipient: str,
    reset_url: str,
    expires_minutes: int,
    sender: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Redefinição de senha · Nexyra CRM"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Recebemos uma solicitação para redefinir sua senha do Nexyra CRM.\n\n"
        f"Abra o link abaixo em até {expires_minutes} minutos:\n"
        f"{reset_url}\n\n"
        "Se você não solicitou esta alteração, ignore esta mensagem. "
        "O link só pode ser usado uma vez.\n"
    )
    return message


def deliver_password_reset(
    *,
    email: str,
    token: str,
    settings: Settings,
) -> PasswordResetDeliveryResult:
    mode = settings.auth_password_reset_delivery.strip().lower()
    reset_url = build_password_reset_url(
        settings.auth_password_reset_frontend_url,
        token,
    )

    if mode == "disabled":
        return PasswordResetDeliveryResult(channel="disabled", delivered=False)

    if mode == "console":
        if settings.environment.strip().lower() == "production":
            raise PasswordResetDeliveryError(
                "Entrega de recuperação por console não é permitida em produção."
            )
        logger.warning(
            "NEXYRA CRM · link local de recuperação para %s: %s",
            email,
            reset_url,
        )
        return PasswordResetDeliveryResult(channel="console", delivered=True)

    if mode != "smtp":
        raise PasswordResetDeliveryError(
            "AUTH_PASSWORD_RESET_DELIVERY deve ser console, smtp ou disabled."
        )

    if not settings.auth_smtp_host or not settings.auth_smtp_from:
        raise PasswordResetDeliveryError(
            "SMTP de recuperação não está configurado."
        )

    message = _smtp_message(
        recipient=email,
        reset_url=reset_url,
        expires_minutes=settings.auth_password_reset_minutes,
        sender=settings.auth_smtp_from,
    )

    try:
        smtp_cls = smtplib.SMTP_SSL if settings.auth_smtp_ssl else smtplib.SMTP
        with smtp_cls(
            settings.auth_smtp_host,
            settings.auth_smtp_port,
            timeout=12,
        ) as client:
            if settings.auth_smtp_starttls and not settings.auth_smtp_ssl:
                client.starttls()
            if settings.auth_smtp_username:
                client.login(
                    settings.auth_smtp_username,
                    settings.auth_smtp_password,
                )
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise PasswordResetDeliveryError(
            "Falha ao entregar a recuperação por e-mail."
        ) from exc

    return PasswordResetDeliveryResult(channel="smtp", delivered=True)
