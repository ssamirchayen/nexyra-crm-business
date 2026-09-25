from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _workspace(client: TestClient, slug: str = "distribution-demo") -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra Distribuição",
            "slug": slug,
            "segment": "education",
        },
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _member(
    client: TestClient,
    workspace_id: str,
    *,
    name: str,
    email: str,
    role: str = "seller",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"name": name, "email": email, "role": role},
    )
    assert response.status_code == 201
    return response.json()


def _enable(
    client: TestClient,
    workspace_id: str,
    *,
    strategy: str = "least_loaded",
    eligible_user_public_ids: list[str] | None = None,
    rules: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    response = client.put(
        f"/api/v1/workspaces/{workspace_id}/lead-distribution/config",
        json={
            "enabled": True,
            "strategy": strategy,
            "eligible_roles": ["seller"],
            "eligible_user_public_ids": eligible_user_public_ids or [],
            "rules": rules or [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _lead(
    client: TestClient,
    workspace_id: str,
    index: int,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"Lead {index}",
        "phone": f"9299000{index:04d}",
        "interest": "Radiologia",
        "source": "site",
        "channel": "web",
        "priority": "media",
        "custom_fields": {"curso": "Radiologia"},
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_distribution_defaults_are_safe_and_disabled(client: TestClient) -> None:
    workspace_id = _workspace(client)
    _member(
        client,
        workspace_id,
        name="Consultor 1",
        email="consultor1@demo.local",
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-distribution/summary"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["enabled"] is False
    assert payload["config"]["strategy"] == "least_loaded"
    assert payload["unassigned_active_leads"] == 0

    lead = _lead(client, workspace_id, 1)
    assert lead["owner_user_public_id"] is None


def test_least_loaded_balances_new_leads(client: TestClient) -> None:
    workspace_id = _workspace(client, "least-loaded")
    seller_a = _member(
        client,
        workspace_id,
        name="Ana",
        email="ana@demo.local",
    )
    seller_b = _member(
        client,
        workspace_id,
        name="Bruno",
        email="bruno@demo.local",
    )
    _enable(client, workspace_id)

    owners = [
        _lead(client, workspace_id, index)["owner_user_public_id"]
        for index in range(1, 5)
    ]

    assert owners.count(seller_a["public_id"]) == 2
    assert owners.count(seller_b["public_id"]) == 2

    summary = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-distribution/summary"
    ).json()
    loads = {
        item["user_public_id"]: item["assigned_active_leads"]
        for item in summary["members"]
    }
    assert loads[seller_a["public_id"]] == 2
    assert loads[seller_b["public_id"]] == 2


def test_rule_routes_priority_and_interest_to_specific_seller(
    client: TestClient,
) -> None:
    workspace_id = _workspace(client, "rules")
    seller_a = _member(
        client,
        workspace_id,
        name="Ana",
        email="ana-rules@demo.local",
    )
    seller_b = _member(
        client,
        workspace_id,
        name="Bruno",
        email="bruno-rules@demo.local",
    )
    _enable(
        client,
        workspace_id,
        eligible_user_public_ids=[
            str(seller_a["public_id"]),
            str(seller_b["public_id"]),
        ],
        rules=[
            {
                "name": "Radiologia Instagram Alta",
                "source": "instagram",
                "interest_contains": "Radiologia",
                "priorities": ["alta", "urgente"],
                "eligible_user_public_ids": [seller_b["public_id"]],
                "strategy": "round_robin",
            }
        ],
    )

    matched = _lead(
        client,
        workspace_id,
        1,
        source="instagram",
        channel="social",
        priority="alta",
    )
    assert matched["owner_user_public_id"] == seller_b["public_id"]

    regular = _lead(client, workspace_id, 2, source="site", priority="media")
    assert regular["owner_user_public_id"] in {
        seller_a["public_id"],
        seller_b["public_id"],
    }


def test_manual_owner_is_never_overridden(client: TestClient) -> None:
    workspace_id = _workspace(client, "manual-owner")
    seller_a = _member(
        client,
        workspace_id,
        name="Ana",
        email="ana-manual@demo.local",
    )
    _member(
        client,
        workspace_id,
        name="Bruno",
        email="bruno-manual@demo.local",
    )
    _enable(client, workspace_id, strategy="round_robin")

    lead = _lead(
        client,
        workspace_id,
        1,
        owner_user_public_id=seller_a["public_id"],
    )
    assert lead["owner_user_public_id"] == seller_a["public_id"]


def test_batch_can_preview_then_assign_existing_unassigned_leads(
    client: TestClient,
) -> None:
    workspace_id = _workspace(client, "batch")
    seller = _member(
        client,
        workspace_id,
        name="Ana",
        email="ana-batch@demo.local",
    )

    first = _lead(client, workspace_id, 1)
    second = _lead(client, workspace_id, 2)
    assert first["owner_user_public_id"] is None
    assert second["owner_user_public_id"] is None

    _enable(client, workspace_id)

    preview = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-distribution/run",
        json={"limit": 100, "dry_run": True},
    )
    assert preview.status_code == 200
    assert preview.json()["assigned"] == 2

    still_unassigned = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search?unassigned=true"
    ).json()
    assert still_unassigned["total"] == 2

    executed = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-distribution/run",
        json={"limit": 100, "dry_run": False},
    )
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["assigned"] == 2
    assert {item["user_public_id"] for item in payload["assignments"]} == {
        seller["public_id"]
    }

    assigned = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search?unassigned=true"
    ).json()
    assert assigned["total"] == 0


def test_non_eligible_role_is_not_selected(client: TestClient) -> None:
    workspace_id = _workspace(client, "roles")
    seller = _member(
        client,
        workspace_id,
        name="Seller",
        email="seller@roles.local",
        role="seller",
    )
    _member(
        client,
        workspace_id,
        name="Operator",
        email="operator@roles.local",
        role="operator",
    )
    _enable(client, workspace_id)

    lead = _lead(client, workspace_id, 1)
    assert lead["owner_user_public_id"] == seller["public_id"]
