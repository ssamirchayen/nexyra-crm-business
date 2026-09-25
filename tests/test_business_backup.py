import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.business_backup import BackupError, manifest_path, seal, verify

DATA = b"PGDMP" + bytes(range(256)) * 100


def partial_file(tmp_path):
    partial = tmp_path / "example.dump.partial"
    partial.write_bytes(DATA)
    return partial


def test_seal_and_verify_preserve_binary_bytes(tmp_path):
    partial = partial_file(tmp_path)
    archive = seal(partial)
    assert archive.read_bytes() == DATA
    assert not partial.exists()
    metadata = verify(archive)
    assert metadata["filename"] == "example.dump"
    assert metadata["size_bytes"] == len(DATA)
    assert set(metadata) == {
        "format_version",
        "format",
        "filename",
        "size_bytes",
        "sha256",
        "created_at",
    }


@pytest.mark.parametrize("existing", ["archive", "manifest"])
def test_existing_backup_never_overwritten(tmp_path, existing):
    partial = partial_file(tmp_path)
    archive = partial.with_suffix("")
    target = archive if existing == "archive" else manifest_path(archive)
    target.write_bytes(b"keep this")
    with pytest.raises(BackupError, match="Já existe"):
        seal(partial)
    assert target.read_bytes() == b"keep this"
    assert partial.read_bytes() == DATA


@pytest.mark.parametrize(
    "data", [b"", b"PGDMP", b"plain SQL is not a custom dump" * 10]
)
def test_invalid_archive_not_published(tmp_path, data):
    partial = partial_file(tmp_path)
    partial.write_bytes(data)
    with pytest.raises(BackupError):
        seal(partial)
    assert not partial.with_suffix("").exists()


def test_manifest_failure_preserves_source_and_cleans_incomplete_output(
    tmp_path, monkeypatch
):
    partial = partial_file(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", fail)
    with pytest.raises(OSError, match="disk full"):
        seal(partial)
    assert partial.read_bytes() == DATA
    assert not partial.with_suffix("").exists()
    assert not manifest_path(partial.with_suffix("")).exists()


@pytest.mark.parametrize(
    "change",
    [
        "tampered",
        "truncated",
        "missing_manifest",
        "invalid_manifest",
        "wrong_filename",
        "wrong_size",
    ],
)
def test_verify_detects_corruption(tmp_path, change):
    archive = seal(partial_file(tmp_path))
    manifest = manifest_path(archive)
    if change == "tampered":
        archive.write_bytes(DATA[:-1] + b"x")
    elif change == "truncated":
        archive.write_bytes(DATA[:100])
    elif change == "missing_manifest":
        manifest.unlink()
    elif change == "invalid_manifest":
        manifest.write_text("not json")
    else:
        metadata = json.loads(manifest.read_text())
        metadata["filename" if change == "wrong_filename" else "size_bytes"] = (
            "other.dump" if change == "wrong_filename" else 1
        )
        manifest.write_text(json.dumps(metadata))
    with pytest.raises((ValueError, OSError)):
        verify(archive)


def test_cli_failure_returns_nonzero_and_success_has_no_app_dependency(tmp_path):
    script = Path("tools/business_backup.py").resolve()
    archive = seal(partial_file(tmp_path))
    result = subprocess.run(
        [sys.executable, str(script), "verify", str(archive)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0
    archive.write_bytes(b"bad")
    result = subprocess.run(
        [sys.executable, str(script), "verify", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Falha no backup" in result.stderr


@pytest.mark.skipif(
    shutil.which("sh") is None,
    reason="requires POSIX sh, as used by PostgreSQL container",
)
@pytest.mark.parametrize("failure", ["none", "dump", "catalog"])
def test_real_dump_shell_command_preserves_arguments_and_stops_on_failure(
    tmp_path, failure
):
    # Run the exact embedded command against stub executables: no live database.
    source = Path("tools/business_backup.ps1").read_text()
    command = re.search(r"\$DumpCommand = '([^']+)'", source).group(1)
    for name in ("pg_dump", "pg_restore"):
        executable = tmp_path / name
        executable.write_text(
            '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$BACKUP_TEST_LOG/'
            + name
            + '.args"\n'
            + (
                "exit 1\n"
                if (name == "pg_dump" and failure == "dump")
                or (name == "pg_restore" and failure == "catalog")
                else "exit 0\n"
            )
        )
        executable.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
        POSTGRES_USER="user with spaces",
        POSTGRES_DB="db ; $(false) *",
        BACKUP_TEST_LOG=str(tmp_path),
    )
    result = subprocess.run(
        ["sh", "-c", command, "sh", "/tmp/archive name.dump"],
        env=env,
        capture_output=True,
        check=False,
    )
    assert (result.returncode == 0) == (failure == "none")
    args = (tmp_path / "pg_dump.args").read_text().splitlines()
    assert args == [
        "--username=user with spaces",
        "--dbname=db ; $(false) *",
        "--format=custom",
        "--file=/tmp/archive name.dump",
    ]
    if failure == "dump":
        assert not (tmp_path / "pg_restore.args").exists()
    else:
        assert (tmp_path / "pg_restore.args").read_text().splitlines() == [
            "--list",
            "/tmp/archive name.dump",
        ]
