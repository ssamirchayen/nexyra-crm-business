from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AuditEvent, AuthSession, PasswordResetRequest
from app.services.auth import AuthService, PasswordRecoveryError

PASSWORD = "Nexyra@Temp123"
NEW_PASSWORD = "Nexyra@Recover456"
EMAIL = "recover@nexyra.demo"


@pytest.fixture
def client_and_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client, testing_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _bootstrap(client: TestClient) -> dict[str, object]:
    workspace = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Recovery Demo",
            "slug": "recovery-demo",
            "segment": "generic",
        },
    ).json()
    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Recovery User",
            "email": EMAIL,
            "role": "admin",
            "initial_password": PASSWORD,
        },
    )
    assert response.status_code == 201
    return workspace


def _login(client: TestClient, password: str = PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_request_endpoint_is_generic_for_known_and_unknown_accounts(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    _bootstrap(client)

    known = client.post(
        "/api/v1/auth/password-recovery/request",
        json={"email": EMAIL},
    )
    unknown = client.post(
        "/api/v1/auth/password-recovery/request",
        json={"email": "unknown@nexyra.demo"},
    )

    assert known.status_code == 202
    assert unknown.status_code == 202
    assert known.json() == unknown.json()
    assert "token" not in known.text.lower()

    with testing_session() as db:
        stored = list(db.scalars(select(PasswordResetRequest)).all())
        assert len(stored) == 1
        assert len(stored[0].token_hash) == 64


def test_valid_reset_is_single_use_and_revokes_sessions(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    _bootstrap(client)
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    with testing_session() as db:
        prepared = AuthService(db).prepare_password_recovery(email=EMAIL)
        assert prepared is not None
        raw_token = prepared.token

    reset = client.post(
        "/api/v1/auth/password-recovery/reset",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    reused = client.post(
        "/api/v1/auth/password-recovery/reset",
        json={"token": raw_token, "new_password": "Nexyra@Another789"},
    )
    assert reused.status_code == 400
    assert reused.json()["detail"] == "Link de recuperação inválido ou expirado."

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200

    with testing_session() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash.is_not(None)))
        assert session is not None
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.workspace_id == db.scalar(
                        select(AuditEvent.workspace_id).where(
                            AuditEvent.action == "auth.password_recovery.completed"
                        )
                    )
                )
            ).all()
        )
        actions = {event.action for event in events}
        assert "auth.password_recovery.requested" in actions
        assert "auth.password_recovery.completed" in actions


def test_expired_token_is_rejected(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    _bootstrap(client)

    with testing_session() as db:
        prepared = AuthService(db).prepare_password_recovery(email=EMAIL)
        assert prepared is not None
        stored = db.scalar(select(PasswordResetRequest))
        assert stored is not None
        stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(stored)
        db.commit()
        raw_token = prepared.token

    response = client.post(
        "/api/v1/auth/password-recovery/reset",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Link de recuperação inválido ou expirado."


def test_invalid_token_is_rejected(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    _bootstrap(client)

    response = client.post(
        "/api/v1/auth/password-recovery/reset",
        json={"token": "x" * 64, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400


def test_same_password_cannot_be_used_during_recovery(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    _bootstrap(client)

    with testing_session() as db:
        prepared = AuthService(db).prepare_password_recovery(email=EMAIL)
        assert prepared is not None
        with pytest.raises(PasswordRecoveryError, match="diferente"):
            AuthService(db).reset_password_with_token(
                token=prepared.token,
                new_password=PASSWORD,
            )
