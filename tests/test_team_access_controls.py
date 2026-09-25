import pytest
from sqlalchemy import select
from test_admin_sessions import (
    client_and_session as client_and_session,  # noqa: PLC0414 - pytest fixture re-export
)
from test_admin_sessions import setup_accounts

from app.models import AuditEvent, User, WorkspaceMembership


def member_path(workspace, user):
    return f"/api/v1/workspaces/{workspace}/members/{user}"


@pytest.mark.parametrize("role", ["admin", "manager"])
def test_manager_cannot_create_privileged_member(client_and_session, role):
    client, factory = client_and_session
    workspace, _, headers, _ = setup_accounts(client, factory)
    response = client.post(
        f"/api/v1/workspaces/{workspace}/members",
        headers=headers["manager"],
        json={
            "name": "Privileged",
            "email": "privileged@example.test",
            "role": role,
        },
    )
    assert response.status_code == 403
    with factory() as db:
        assert (
            db.scalar(select(User).where(User.email == "privileged@example.test"))
            is None
        )


@pytest.mark.parametrize(
    "target,changes",
    [
        ("manager", {"role": "admin"}),
        ("manager", {"role": "seller"}),
        ("admin", {"role": "seller"}),
        ("seller", {"role": "admin"}),
        ("seller", {"role": "manager"}),
        ("seller", {"active": False}),
        ("operator", {"role": "seller", "active": False}),
    ],
)
def test_manager_cannot_bypass_role_or_status_limits(
    client_and_session, target, changes
):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = member_path(workspace, users[target])
    before = client.get(path, headers=headers["admin"]).json()
    assert (
        client.patch(path, headers=headers["manager"], json=changes).status_code == 403
    )
    assert client.get(path, headers=headers["admin"]).json() == before
    with factory() as db:
        assert (
            db.scalar(
                select(AuditEvent).where(AuditEvent.action == "membership.updated")
            )
            is None
        )


def test_manager_can_create_and_edit_operational_members(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    response = client.post(
        f"/api/v1/workspaces/{workspace}/members",
        headers=headers["manager"],
        json={
            "name": "New seller",
            "email": "new@example.test",
            "role": "seller",
            "initial_password": "Nexyra@Temp123",
        },
    )
    assert response.status_code == 201
    response = client.patch(
        member_path(workspace, users["seller"]),
        headers=headers["manager"],
        json={
            "role": "operator",
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "operator"
    with factory() as db:
        audit = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "membership.updated")
        )
        assert audit.actor_membership_id is not None


@pytest.mark.parametrize(
    "method,body",
    [
        ("patch", {"role": "manager"}),
        ("patch", {"active": False}),
        ("post", None),
    ],
)
def test_last_administrator_cannot_be_removed(client_and_session, method, body):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = member_path(workspace, users["admin"])
    response = (
        client.post(path + "/deactivate", headers=headers["admin"])
        if method == "post"
        else client.patch(path, headers=headers["admin"], json=body)
    )
    assert response.status_code == 409
    assert (
        client.get(path, headers=headers["admin"]).json()["membership_active"] is True
    )
    assert client.get(path, headers=headers["admin"]).json()["role"] == "admin"


def test_admin_without_password_is_not_a_replacement(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    response = client.post(
        f"/api/v1/workspaces/{workspace}/members",
        headers=headers["admin"],
        json={
            "name": "No password",
            "email": "no-password@example.test",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    assert (
        client.patch(
            member_path(workspace, users["admin"]),
            headers=headers["admin"],
            json={"role": "seller"},
        ).status_code
        == 409
    )


def test_second_admin_allows_demotion_and_permissions_change_immediately(
    client_and_session,
):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    replacement = member_path(workspace, users["manager"])
    assert (
        client.patch(
            replacement, headers=headers["admin"], json={"role": "admin"}
        ).status_code
        == 200
    )
    own = member_path(workspace, users["admin"])
    assert (
        client.patch(
            own, headers=headers["admin"], json={"role": "manager"}
        ).status_code
        == 200
    )
    assert (
        client.patch(own, headers=headers["admin"], json={"role": "admin"}).status_code
        == 403
    )
    assert client.get(own + "/sessions", headers=headers["admin"]).status_code == 403
    assert (
        client.get(replacement + "/sessions", headers=headers["manager"]).status_code
        == 200
    )
    # It is now the replacement who must not be removed.
    assert (
        client.post(replacement + "/deactivate", headers=headers["manager"]).status_code
        == 409
    )


def test_admin_can_toggle_members_and_manager_cannot_reactivate(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = member_path(workspace, users["seller"])
    assert (
        client.post(path + "/deactivate", headers=headers["admin"]).status_code == 200
    )
    assert (
        client.patch(
            path, headers=headers["manager"], json={"active": True}
        ).status_code
        == 403
    )
    assert client.get(
        f"/api/v1/workspaces/{workspace}/members", headers=headers["seller"]
    ).status_code in {401, 403}
    assert (
        client.patch(path, headers=headers["admin"], json={"active": True}).status_code
        == 200
    )


@pytest.mark.parametrize("role", ["seller", "operator"])
def test_readonly_team_profiles_cannot_write(client_and_session, role):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = member_path(workspace, users["seller"])
    assert (
        client.patch(path, headers=headers[role], json={"role": "admin"}).status_code
        == 403
    )
    assert client.post(path + "/deactivate", headers=headers[role]).status_code == 403
    assert (
        client.post(
            f"/api/v1/workspaces/{workspace}/members",
            headers=headers[role],
            json={
                "name": "Other",
                "email": "other@example.test",
                "role": "seller",
            },
        ).status_code
        == 403
    )


@pytest.mark.parametrize("field", ["active", "role"])
def test_null_patch_fields_rejected(client_and_session, field):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    assert (
        client.patch(
            member_path(workspace, users["seller"]),
            headers=headers["admin"],
            json={field: None},
        ).status_code
        == 422
    )


def test_inactive_admin_not_counted_as_replacement(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    with factory() as db:
        member = db.scalar(
            select(WorkspaceMembership)
            .join(User)
            .where(User.public_id == users["manager"])
        )
        member.role = "admin"
        member.active = False
        db.commit()
    assert (
        client.post(
            member_path(workspace, users["admin"]) + "/deactivate",
            headers=headers["admin"],
        ).status_code
        == 409
    )
