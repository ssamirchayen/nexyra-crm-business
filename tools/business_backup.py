"""Finalize and verify PostgreSQL backup files without loading app settings."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


class BackupError(ValueError):
    pass


def manifest_path(archive: Path) -> Path:
    return archive.with_name(archive.name + ".sha256.json")


def _digest(archive: Path) -> tuple[str, int]:
    if archive.is_symlink():
        raise BackupError("O arquivo de backup não pode ser um link simbólico.")
    digest = hashlib.sha256()
    size = 0
    with archive.open("rb") as stream:
        if stream.read(5) != b"PGDMP":
            raise BackupError("O arquivo não é um dump PostgreSQL no formato custom.")
        stream.seek(0)
        while block := stream.read(CHUNK_SIZE):
            digest.update(block)
            size += len(block)
    if size < 32:
        raise BackupError("Arquivo de backup incompleto.")
    return digest.hexdigest(), size


def seal(partial: Path) -> Path:
    """Publish an archive and manifest; never overwrite an earlier backup."""
    if not partial.name.endswith(".dump.partial"):
        raise BackupError("O arquivo temporário deve terminar em .dump.partial.")
    sha256, size = _digest(partial)
    archive = partial.with_suffix("")
    manifest = manifest_path(archive)
    if (
        archive.exists()
        or archive.is_symlink()
        or manifest.exists()
        or manifest.is_symlink()
    ):
        raise BackupError("Já existe um backup com este nome; nada foi substituído.")
    created_archive = False
    created_manifest = False
    try:
        # Exclusive creation also protects against a concurrent same-name writer.
        with archive.open("xb") as destination:
            created_archive = True
            copied_digest = hashlib.sha256()
            copied_size = 0
            with partial.open("rb") as source:
                while block := source.read(CHUNK_SIZE):
                    destination.write(block)
                    copied_digest.update(block)
                    copied_size += len(block)
            if copied_digest.hexdigest() != sha256 or copied_size != size:
                raise BackupError("O arquivo temporário mudou durante a cópia.")
            destination.flush()
            os.fsync(destination.fileno())
        metadata = {
            "format_version": 1,
            "format": "postgresql-custom",
            "filename": archive.name,
            "size_bytes": size,
            "sha256": sha256,
            "created_at": datetime.now(UTC).isoformat(),
        }
        with manifest.open("x", encoding="utf-8") as stream:
            created_manifest = True
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if created_manifest:
            manifest.unlink(missing_ok=True)
        if created_archive:
            archive.unlink(missing_ok=True)
        raise
    # A leftover partial is harmless; the verified pair is already complete.
    try:
        partial.unlink()
    except OSError:
        pass
    return archive


def verify(archive: Path) -> dict:
    if archive.suffix != ".dump":
        raise BackupError("Selecione um arquivo .dump finalizado.")
    manifest = manifest_path(archive)
    if manifest.is_symlink() or manifest.stat().st_size > 65536:
        raise BackupError("Manifesto de backup inválido.")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or (
        metadata.get("format_version") != 1
        or metadata.get("format") != "postgresql-custom"
        or metadata.get("filename") != archive.name
        or not isinstance(metadata.get("size_bytes"), int)
        or not re.fullmatch(r"[0-9a-f]{64}", str(metadata.get("sha256", "")))
    ):
        raise BackupError("Manifesto incompatível com este backup.")
    sha256, size = _digest(archive)
    if sha256 != metadata["sha256"] or size != metadata["size_bytes"]:
        raise BackupError(
            "Falha de integridade: o backup foi alterado ou está incompleto."
        )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "verify"))
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "seal":
            archive = seal(args.file)
            print(f"Backup finalizado: {archive.name}")
        else:
            metadata = verify(args.file)
            print(f"Integridade SHA-256 confirmada: {metadata['filename']}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Falha no backup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
