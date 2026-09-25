"""Validate sanitized results from an isolated PostgreSQL restore check."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_DATABASE = "nexyra_restore_check"
EXPECTED_REVISION = "0018_create_communication_consents"
TABLES = (
    "workspaces",
    "users",
    "workspace_memberships",
    "user_credentials",
    "leads",
    "opportunities",
    "activities",
    "audit_events",
)


def build_report(result: dict, backup_name: str, sha256: str) -> dict:
    if not isinstance(result, dict):
        raise TypeError("Resultado da consulta inválido.")
    if result.get("database") != EXPECTED_DATABASE:
        raise ValueError("O resultado não pertence ao banco temporário esperado.")
    version = result.get("server_version_num")
    if type(version) is not int or version // 10000 != 16:
        raise ValueError("O teste exige PostgreSQL 16.")
    if result.get("revisions") != [EXPECTED_REVISION]:
        raise ValueError(
            "A revisão do banco não corresponde à versão atual do Business."
        )
    counts = result.get("counts")
    if not isinstance(counts, dict) or any(
        type(counts.get(table)) is not int or counts[table] < 0 for table in TABLES
    ):
        raise ValueError("Contagens ausentes ou inválidas para as tabelas principais.")
    if (
        type(result.get("orphan_memberships")) is not int
        or result["orphan_memberships"] != 0
    ):
        raise ValueError("Foram encontrados vínculos de equipe sem usuário ou empresa.")
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("SHA-256 inválido.")
    if not backup_name.endswith(".dump") or "/" in backup_name or "\\" in backup_name:
        raise ValueError("Nome do backup inválido.")
    # Copy only approved aggregate fields, never arbitrary database output.
    return {
        "format_version": 1,
        "status": "passed",
        "checked_at": datetime.now(UTC).isoformat(),
        "backup_filename": backup_name,
        "backup_sha256": sha256,
        "postgresql_version_num": version,
        "revision": EXPECTED_REVISION,
        "row_counts": {table: counts[table] for table in TABLES},
        "orphan_memberships": 0,
        "scope": "isolated_restore_and_core_tables",
        "application_login_tested": False,
    }


def application_checks(source: Path, check_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", check_id) or source.stat().st_size > 65536:
        raise ValueError("Identificação ou tamanho inválido no teste da aplicação.")
    data = json.loads(source.read_text(encoding="utf-8"))
    required = ("ready", "login", "identity", "members", "logout", "revoked_token")
    if (
        not isinstance(data, dict)
        or data.get("status") != "passed"
        or data.get("subject") != "temporary_test_user"
        or data.get("restore_check_id") != check_id
        or not isinstance(data.get("checks"), dict)
        or any(data["checks"].get(key) is not True for key in required)
        or data.get("real_user_passwords_tested") is not False
        or data.get("external_integrations_tested") is not False
    ):
        raise ValueError(
            "Teste de aplicação incompleto ou incompatível com esta execução."
        )
    return {
        "subject": "temporary_test_user",
        "checks": dict.fromkeys(required, True),
        "real_user_passwords_tested": False,
        "external_integrations_tested": False,
    }


def write_report(
    source: Path,
    output: Path,
    backup_name: str,
    sha256: str,
    application_check: Path | None = None,
    check_id: str | None = None,
) -> None:
    if source.stat().st_size > 65536:
        raise ValueError("Resultado maior que o limite esperado.")
    result = json.loads(source.read_text(encoding="utf-8-sig"))
    report = build_report(result, backup_name, sha256)
    if application_check is not None:
        report["application_check"] = application_checks(
            application_check, check_id or ""
        )
        report["application_login_tested"] = True
        report["scope"] = "isolated_restore_core_tables_and_synthetic_login"
    created = False
    try:
        with output.open("x", encoding="utf-8") as stream:
            created = True
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backup-name", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--application-check", type=Path)
    parser.add_argument("--check-id")
    args = parser.parse_args()
    try:
        write_report(
            args.source,
            args.output,
            args.backup_name,
            args.sha256,
            args.application_check,
            args.check_id,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Falha na conferência da restauração: {exc}", file=sys.stderr)
        return 1
    print("Restauração isolada e tabelas principais conferidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
