from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_admin_sessions import (
    client_and_session as client_and_session,  # noqa: PLC0414 - pytest fixture re-export
)
from test_admin_sessions import setup_accounts

from app.models import (
    AuditEvent,
    AuthSession,
    PasswordResetRequest,
    User,
    UserCredential,
    Workspace,
    WorkspaceMembership,
)
from app.security import hash_password_reset_token, verify_password

PASSWORD = "Nexyra@Temp123"


def reset_path(workspace, user):
    return f"/api/v1/workspaces/{workspace}/members/{user}/reset-password"


def test_reset_revokes_every_session_and_requires_password_change(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    recovery_token = "r" * 48
    with factory() as db:
        user = db.scalar(select(User).where(User.public_id == users["seller"]))
        user_id = user.id
        for i in range(25):
            db.add(
                AuthSession(
                    user_id=user.id,
                    token_hash=f"{i:064x}",
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
        db.add(
            PasswordResetRequest(
                user_id=user.id,
                token_hash=hash_password_reset_token(recovery_token),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        db.commit()
    response = client.post(
        reset_path(workspace, users["seller"]),
        headers=headers["admin"],
        json={"current_password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    temporary = response.json()["temporary_password"]
    assert len(temporary) >= 24
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["must_change_password"] is True
    assert client.get("/api/v1/auth/me", headers=headers["seller"]).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers["admin"]).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "seller@example.test", "password": PASSWORD},
        ).status_code
        == 401
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "seller@example.test", "password": temporary},
    )
    assert login.status_code == 200
    new_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (
        client.get(
            f"/api/v1/workspaces/{workspace}/members", headers=new_headers
        ).status_code
        == 403
    )
    with factory() as db:
        old_sessions = db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_reason == "password_reset_by_admin",
            )
        ).all()
        assert len(old_sessions) == 26
        request = db.scalar(
            select(PasswordResetRequest).where(PasswordResetRequest.user_id == user_id)
        )
        assert request.revoked_at is not None
        credential = db.scalar(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        assert credential.password_hash != temporary and verify_password(
            temporary, credential.password_hash
        )
        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "user.password_reset_by_admin"
            )
        )
        assert event.actor_membership_id is not None
        assert event.metadata_json == {"must_change_password": True}
        assert temporary not in str(event.metadata_json)
    assert (
        client.post(
            "/api/v1/auth/password-recovery/reset",
            json={"token": recovery_token, "new_password": "Nexyra@Nova123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/change-password",
            headers=new_headers,
            json={
                "current_password": temporary,
                "new_password": "Nexyra@Nova123",
            },
        ).status_code
        == 200
    )
    final = client.post(
        "/api/v1/auth/login",
        json={"email": "seller@example.test", "password": "Nexyra@Nova123"},
    )
    assert final.status_code == 200
    assert final.json()["user"]["must_change_password"] is False


@pytest.mark.parametrize("role", ["manager", "seller", "operator"])
def test_only_admin_can_reset_password(client_and_session, role):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    response = client.post(
        reset_path(workspace, users["seller"]),
        headers=headers[role],
        json={"current_password": PASSWORD},
    )
    assert response.status_code == 403


def test_wrong_confirmation_and_lockout_do_not_change_target(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = reset_path(workspace, users["seller"])
    for _ in range(4):
        assert (
            client.post(
                path, headers=headers["admin"], json={"current_password": "wrong"}
            ).status_code
            == 403
        )
    response = client.post(
        path, headers=headers["admin"], json={"current_password": "wrong"}
    )
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    assert (
        client.post(
            path, headers=headers["admin"], json={"current_password": PASSWORD}
        ).status_code
        == 429
    )
    assert client.get("/api/v1/auth/me", headers=headers["seller"]).status_code == 200
    with factory() as db:
        user = db.scalar(select(User).where(User.public_id == users["seller"]))
        credential = db.scalar(
            select(UserCredential).where(UserCredential.user_id == user.id)
        )
        assert verify_password(PASSWORD, credential.password_hash)
        assert (
            db.scalar(
                select(AuditEvent).where(
                    AuditEvent.action == "user.password_reset_by_admin"
                )
            )
            is None
        )


@pytest.mark.parametrize(
    "condition,status",
    [
        ("self", 409),
        ("missing", 404),
        ("inactive", 409),
        ("shared", 409),
        ("foreign", 403),
    ],
)
def test_reset_account_boundaries(client_and_session, condition, status):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    user_public_id = users["seller"]
    if condition == "self":
        user_public_id = users["admin"]
    elif condition == "missing":
        user_public_id = "USR-missing"
    elif condition in {"shared", "foreign", "inactive"}:
        with factory() as db:
            user = db.scalar(select(User).where(User.public_id == user_public_id))
            if condition == "inactive":
                db.scalar(
                    select(WorkspaceMembership).where(
                        WorkspaceMembership.user_id == user.id
                    )
                ).active = False
            else:
                other = Workspace(name="Other", slug="other", segment="generic")
                db.add(other)
                db.flush()
                db.add(
                    WorkspaceMembership(
                        workspace_id=other.id,
                        user_id=user.id,
                        role="seller",
                        active=False,
                    )
                )
                if condition == "foreign":
                    workspace = other.public_id
            db.commit()
    assert (
        client.post(
            reset_path(workspace, user_public_id),
            headers=headers["admin"],
            json={"current_password": PASSWORD},
        ).status_code
        == status
    )


def test_password_can_be_configured_for_member_without_credentials(client_and_session):
    client, factory = client_and_session
    workspace, _, headers, _ = setup_accounts(client, factory)
    member = client.post(
        f"/api/v1/workspaces/{workspace}/members",
        headers=headers["admin"],
        json={
            "name": "New user",
            "email": "new@example.test",
            "role": "seller",
        },
    ).json()
    response = client.post(
        reset_path(workspace, member["public_id"]),
        headers=headers["admin"],
        json={"current_password": PASSWORD},
    )
    assert response.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "new@example.test",
            "password": response.json()["temporary_password"],
        },
    )
    assert login.status_code == 200
    assert login.json()["user"]["must_change_password"] is True


def test_reset_is_atomic_if_audit_fails(client_and_session, monkeypatch):
    from app.services.audit import AuditService

    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)

    def fail(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError, match="audit failed"):
        client.post(
            reset_path(workspace, users["seller"]),
            headers=headers["admin"],
            json={"current_password": PASSWORD},
        )
    assert client.get("/api/v1/auth/me", headers=headers["seller"]).status_code == 200
    with factory() as db:
        user = db.scalar(select(User).where(User.public_id == users["seller"]))
        credential = db.scalar(
            select(UserCredential).where(UserCredential.user_id == user.id)
        )
        assert verify_password(PASSWORD, credential.password_hash)


def test_bootstrap_cannot_reset_passwords(client_and_session):
    client, _ = client_and_session
    assert (
        client.post(
            reset_path("unknown", "unknown"), json={"current_password": PASSWORD}
        ).status_code
        == 401
    )
