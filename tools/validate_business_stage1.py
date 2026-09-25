from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.runtime import database_backend, normalize_database_url


def check_online(base_url: str) -> list[str]:
    errors: list[str] = []
    for path in ("/api/v1/health", "/api/v1/health/ready"):
        url = base_url.rstrip("/") + path
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status != 200 or not payload.get("ok"):
                    errors.append(f"{path}: resposta inesperada")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    settings = get_settings()
    backend = database_backend(settings.database_url)
    print(f"[OK] deployment_mode={settings.deployment_mode}")
    print(f"[OK] database_backend={backend}")
    print(f"[OK] pool={settings.database_pool_size}+{settings.database_max_overflow}")
    print(f"[OK] URL normalizada usa driver: {normalize_database_url(settings.database_url).split(':', 1)[0]}")

    errors: list[str] = []
    if settings.deployment_mode != "business":
        errors.append("DEPLOYMENT_MODE deve ser business.")
    if settings.database_require_postgresql and backend != "postgresql":
        errors.append("DATABASE_REQUIRE_POSTGRESQL=true, mas DATABASE_URL não é PostgreSQL.")
    if args.online:
        errors.extend(check_online(args.base_url))

    if errors:
        for item in errors:
            print(f"[ERRO] {item}")
        return 1

    print("[OK] Nexyra Business Etapa 1 validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
