"""Exercise local API authentication only inside a guarded restore-test container."""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

CHECKS = ("ready", "login", "identity", "members", "logout", "revoked_token")


class SmokeError(ValueError):
    pass


def guard_environment(env) -> None:
    expected = {
        "NEXYRA_DB_HOST": "restore-db",
        "NEXYRA_DB_NAME": "nexyra_restore_check",
        "NEXYRA_DB_USER": "nexyra_restore",
    }
    if any(
        env.get(key) != value for key, value in expected.items()
    ) or not re.fullmatch(r"[a-f0-9]{32}", env.get("NEXYRA_RESTORE_CHECK_ID", "")):
        raise SmokeError(
            "Execução permitida somente no ambiente temporário de restauração."
        )


def http_request(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, {}  # Never emit response bodies or credentials on failure.


def exercise_auth(
    request, email, password, workspace_id, user_id, *, backend="postgresql"
):
    status, payload = request("GET", "/health/ready")
    if (
        status != 200
        or payload.get("ok") is not True
        or payload.get("database") != backend
    ):
        raise SmokeError("Falha na prontidão da API restaurada.")
    status, login = request(
        "POST", "/auth/login", {"email": email, "password": password}
    )
    if (
        status != 200
        or not isinstance(login.get("access_token"), str)
        or not login["access_token"]
    ):
        raise SmokeError("Falha no login de teste.")
    token = login["access_token"]
    status, identity = request("GET", "/auth/me", token=token)
    if (
        status != 200
        or identity.get("user", {}).get("public_id") != user_id
        or not any(
            w.get("public_id") == workspace_id for w in identity.get("workspaces", [])
        )
    ):
        raise SmokeError("Identidade ou empresa incorreta na sessão de teste.")
    status, members = request("GET", f"/workspaces/{workspace_id}/members", token=token)
    if (
        status != 200
        or not isinstance(members, list)
        or not any(m.get("public_id") == user_id for m in members)
    ):
        raise SmokeError("Falha ao consultar membros com a sessão de teste.")
    status, _ = request("POST", "/auth/logout", token=token)
    if status != 200:
        raise SmokeError("Falha no encerramento da sessão de teste.")
    status, _ = request("GET", "/auth/me", token=token)
    if status != 401:
        raise SmokeError("A API aceitou um token após o encerramento da sessão.")
    return {
        "status": "passed",
        "subject": "temporary_test_user",
        "checks": dict.fromkeys(CHECKS, True),
        "real_user_passwords_tested": False,
        "external_integrations_tested": False,
    }


def create_test_identity():
    # Imports happen only after the environment guard; no app access on import.
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.models import User, UserCredential, Workspace, WorkspaceMembership
    from app.security import hash_password

    suffix = uuid4().hex
    email = f"restore-{suffix}@example.invalid"
    password = "Aa1!" + secrets.token_urlsafe(24)
    with SessionLocal.begin() as db:
        if db.scalar(text("SELECT current_database()")) != "nexyra_restore_check":
            raise SmokeError("O banco conectado não é o banco temporário esperado.")
        workspace = Workspace(
            name="Restore check", slug="restore-" + suffix, segment="generic"
        )
        user = User(name="Restore check", email=email)
        db.add_all([workspace, user])
        db.flush()
        db.add(
            WorkspaceMembership(
                workspace_id=workspace.id, user_id=user.id, role="admin", active=True
            )
        )
        db.add(
            UserCredential(
                user_id=user.id,
                password_hash=hash_password(
                    password,
                    iterations=get_settings().auth_password_iterations,
                ),
                must_change_password=False,
            )
        )
        workspace_id, user_id = workspace.public_id, user.public_id
    return email, password, workspace_id, user_id


def main() -> int:
    try:
        guard_environment(os.environ)
        for _ in range(60):
            try:
                status, data = http_request("GET", "/health/ready")
                if status == 200 and data.get("ok") is True:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise SmokeError("A API temporária não ficou pronta em 60 tentativas.")
        identity = create_test_identity()
        result = exercise_auth(http_request, *identity)
        result["restore_check_id"] = os.environ["NEXYRA_RESTORE_CHECK_ID"]
        with Path("/tmp/application-check.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream)
        print("API, login e encerramento da sessão temporária conferidos.")
        return 0
    except SmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (SQLAlchemyError, OSError, ValueError, TypeError, KeyError, AttributeError):
        # Database exceptions may include connection/credential details.
        print(
            "Falha no teste da aplicação temporária; nenhum resultado foi aprovado.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
