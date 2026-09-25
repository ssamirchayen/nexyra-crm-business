from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

PASSWORD_ALGORITHM = "pbkdf2_sha256"
DEFAULT_MIN_LENGTH = 12


class PasswordStrengthError(ValueError):
    pass


def validate_password_strength(
    password: str,
    *,
    min_length: int = DEFAULT_MIN_LENGTH,
) -> str:
    if len(password) < min_length:
        raise PasswordStrengthError(
            f"A senha deve ter pelo menos {min_length} caracteres."
        )
    if len(password) > 128:
        raise PasswordStrengthError("A senha deve ter no máximo 128 caracteres.")
    if not any(char.islower() for char in password):
        raise PasswordStrengthError("A senha deve conter uma letra minúscula.")
    if not any(char.isupper() for char in password):
        raise PasswordStrengthError("A senha deve conter uma letra maiúscula.")
    if not any(char.isdigit() for char in password):
        raise PasswordStrengthError("A senha deve conter um número.")
    if not any(not char.isalnum() for char in password):
        raise PasswordStrengthError("A senha deve conter um caractere especial.")
    return password


def hash_password(
    password: str,
    *,
    iterations: int,
    min_length: int = DEFAULT_MIN_LENGTH,
) -> str:
    validate_password_strength(password, min_length=min_length)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{PASSWORD_ALGORITHM}${iterations}${salt_b64}${digest_b64}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate, expected)
