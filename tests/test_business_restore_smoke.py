import json

import pytest
from test_admin_sessions import (
    client_and_session as client_and_session,  # noqa: PLC0414 - pytest fixture re-export
)
from test_admin_sessions import setup_accounts
from test_business_restore_report import (
    result as result,  # noqa: PLC0414 - pytest fixture re-export
)

from tools.business_restore_report import application_checks, write_report
from tools.business_restore_smoke import (
    CHECKS,
    SmokeError,
    exercise_auth,
    guard_environment,
)


def client_transport(client):
    def request(method, path, body=None, token=None):
        headers = {"Authorization": "Bearer " + token} if token else {}
        response = client.request(method, "/api/v1" + path, json=body, headers=headers)
        return response.status_code, response.json()

    return request


def test_login_smoke_against_real_api(client_and_session):
    client, factory = client_and_session
    workspace, users, _, _ = setup_accounts(client, factory)
    result = exercise_auth(
        client_transport(client),
        "admin@example.test",
        "Nexyra@Temp123",
        workspace,
        users["admin"],
        backend="sqlite",
    )
    assert result["checks"] == dict.fromkeys(CHECKS, True)
    assert result["status"] == "passed"
    serialized = json.dumps(result)
    assert "access_token" not in serialized and "Nexyra@Temp123" not in serialized
    assert "admin@example.test" not in serialized


@pytest.mark.parametrize(
    "failure", ["ready", "login", "identity", "members", "logout", "revoked_token"]
)
def test_failed_api_step_never_reports_success(client_and_session, failure):
    client, factory = client_and_session
    workspace, users, _, _ = setup_accounts(client, factory)
    underlying = client_transport(client)
    logged_out = False

    def request(method, path, body=None, token=None):
        nonlocal logged_out
        status, payload = underlying(method, path, body, token)
        if path == "/health/ready" and failure == "ready":
            return 503, {}
        if path == "/auth/login" and failure == "login":
            return 401, {}
        if path == "/auth/me" and not logged_out and failure == "identity":
            return 200, {"user": {"public_id": "wrong"}, "workspaces": []}
        if path.endswith("/members") and failure == "members":
            return 200, []
        if path == "/auth/logout":
            logged_out = True
            if failure == "logout":
                return 500, {}
        if path == "/auth/me" and logged_out and failure == "revoked_token":
            return 200, {}
        return status, payload

    with pytest.raises(SmokeError):
        exercise_auth(
            request,
            "admin@example.test",
            "Nexyra@Temp123",
            workspace,
            users["admin"],
            backend="sqlite",
        )


def test_guard_allows_only_restore_environment():
    env = {
        "NEXYRA_DB_HOST": "restore-db",
        "NEXYRA_DB_NAME": "nexyra_restore_check",
        "NEXYRA_DB_USER": "nexyra_restore",
        "NEXYRA_RESTORE_CHECK_ID": "a" * 32,
    }
    guard_environment(env)
    for key in env:
        changed = dict(env)
        changed[key] = "production"
        with pytest.raises(SmokeError):
            guard_environment(changed)
    with pytest.raises(SmokeError):
        guard_environment({})


def application_result():
    return {
        "status": "passed",
        "subject": "temporary_test_user",
        "restore_check_id": "a" * 32,
        "checks": dict.fromkeys(CHECKS, True),
        "real_user_passwords_tested": False,
        "external_integrations_tested": False,
    }


def test_report_includes_verified_application_checks(tmp_path, result):
    source = tmp_path / "database.json"
    source.write_text(json.dumps(result))
    application = tmp_path / "application.json"
    payload = application_result()
    payload["password"] = "do not copy"
    application.write_text(json.dumps(payload))
    output = tmp_path / "report.json"
    write_report(source, output, "backup.dump", "a" * 64, application, "a" * 32)
    report = json.loads(output.read_text())
    assert report["application_login_tested"] is True
    assert report["application_check"]["checks"] == dict.fromkeys(CHECKS, True)
    assert "do not copy" not in output.read_text()


@pytest.mark.parametrize(
    "failure", ["stale", "incomplete", "failed", "wrong_subject", "string_boolean"]
)
def test_bad_application_report_rejected(tmp_path, failure):
    data = application_result()
    if failure == "stale":
        data["restore_check_id"] = "b" * 32
    elif failure == "incomplete":
        del data["checks"]["logout"]
    elif failure == "failed":
        data["status"] = "failed"
    elif failure == "wrong_subject":
        data["subject"] = "real_user"
    else:
        data["checks"]["login"] = "true"
    source = tmp_path / "application.json"
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        application_checks(source, "a" * 32)


def test_bad_application_prevents_final_report(tmp_path, result):
    database = tmp_path / "database.json"
    database.write_text(json.dumps(result))
    application = tmp_path / "application.json"
    application.write_text("{}")
    output = tmp_path / "final.json"
    with pytest.raises(ValueError):
        write_report(database, output, "backup.dump", "a" * 64, application, "a" * 32)
    assert not output.exists()
