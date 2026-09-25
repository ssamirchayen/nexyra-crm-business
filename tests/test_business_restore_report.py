import json
import subprocess
import sys

import pytest

from tools.business_restore_report import (
    EXPECTED_DATABASE,
    EXPECTED_REVISION,
    TABLES,
    build_report,
    write_report,
)


@pytest.fixture
def result():
    return {
        "database": EXPECTED_DATABASE,
        "server_version_num": 160015,
        "revisions": [EXPECTED_REVISION],
        "counts": dict.fromkeys(TABLES, 10),
        "orphan_memberships": 0,
    }


def test_report_is_bound_to_archive_and_only_contains_aggregate_data(result):
    result["email"] = "private@example.test"
    result["password_hash"] = "must not leak"
    report = build_report(result, "backup.dump", "a" * 64)
    assert report["status"] == "passed"
    assert report["backup_sha256"] == "a" * 64
    assert report["row_counts"] == dict.fromkeys(TABLES, 10)
    assert report["application_login_tested"] is False
    assert "private" not in json.dumps(report)
    assert "password_hash" not in json.dumps(report)


@pytest.mark.parametrize(
    "field,value",
    [
        ("database", "nexyra_business"),
        ("server_version_num", 150010),
        ("server_version_num", "160015"),
        ("revisions", []),
        ("revisions", ["older_revision"]),
        ("orphan_memberships", 1),
        ("orphan_memberships", False),
        ("counts", {}),
    ],
)
def test_bad_database_results_are_rejected(result, field, value):
    result[field] = value
    with pytest.raises(ValueError):
        build_report(result, "backup.dump", "a" * 64)


@pytest.mark.parametrize("value", [-1, "10", True, None])
def test_invalid_table_count_rejected(result, value):
    result["counts"]["users"] = value
    with pytest.raises(ValueError):
        build_report(result, "backup.dump", "a" * 64)


def test_empty_database_counts_are_valid(result):
    result["counts"] = dict.fromkeys(TABLES, 0)
    assert build_report(result, "backup.dump", "a" * 64)["status"] == "passed"


def test_report_does_not_replace_earlier_result(tmp_path, result):
    source = tmp_path / "input.json"
    output = tmp_path / "report.json"
    source.write_text(json.dumps(result))
    output.write_text("original")
    with pytest.raises(FileExistsError):
        write_report(source, output, "backup.dump", "a" * 64)
    assert output.read_text() == "original"


def test_cli_does_not_publish_failed_check(tmp_path, result):
    source = tmp_path / "input.json"
    output = tmp_path / "report.json"
    result["orphan_memberships"] = 5
    source.write_text(json.dumps(result))
    process = subprocess.run(
        [
            sys.executable,
            "tools/business_restore_report.py",
            str(source),
            str(output),
            "--backup-name",
            "backup.dump",
            "--sha256",
            "a" * 64,
        ],
        capture_output=True,
        check=False,
    )
    assert process.returncode == 1
    assert not output.exists()


def test_cli_writes_valid_report(tmp_path, result):
    source = tmp_path / "input.json"
    output = tmp_path / "report.json"
    source.write_text(json.dumps(result))
    process = subprocess.run(
        [
            sys.executable,
            "tools/business_restore_report.py",
            str(source),
            str(output),
            "--backup-name",
            "backup.dump",
            "--sha256",
            "a" * 64,
        ],
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0
    assert json.loads(output.read_text())["status"] == "passed"


def test_failed_write_cleans_incomplete_report(tmp_path, result, monkeypatch):
    source = tmp_path / "input.json"
    output = tmp_path / "report.json"
    source.write_text(json.dumps(result))

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", fail)
    with pytest.raises(OSError, match="disk full"):
        write_report(source, output, "backup.dump", "a" * 64)
    assert not output.exists()


def test_report_rejects_oversized_input(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(" " * 65537)
    with pytest.raises(ValueError):
        write_report(source, tmp_path / "report.json", "backup.dump", "a" * 64)


@pytest.mark.parametrize(
    "name,checksum",
    [
        ("../backup.dump", "a" * 64),
        ("backup.sql", "a" * 64),
        ("backup.dump", "invalid"),
    ],
)
def test_backup_identity_is_validated(result, name, checksum):
    with pytest.raises(ValueError):
        build_report(result, name, checksum)
