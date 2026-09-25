from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(prefix="nexyra-release-") as temp_dir:
        db_path = Path(temp_dir) / "nexyra_release_smoke.db"
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        env["ENVIRONMENT"] = "development"

        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            env=env,
            check=True,
        )

        code = (
            "from fastapi.testclient import TestClient; "
            "from app.main import app; "
            "c=TestClient(app); "
            "r=c.get('/api/v1/health'); "
            "assert r.status_code == 200, r.text; "
            "assert r.json()['ok'] is True; "
            "print('Smoke OK:', r.json())"
        )
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=project_root,
            env=env,
            check=True,
        )

    print("Nexyra CRM release smoke test concluído com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
