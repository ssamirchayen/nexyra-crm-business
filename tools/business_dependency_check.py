"""Check the installed production image without importing the application."""

from importlib.metadata import PackageNotFoundError, version


def main() -> int:
    for package in ("pytest", "pytest-cov", "ruff", "pip-audit", "fakeredis"):
        try:
            version(package)
        except PackageNotFoundError:
            continue
        print(f"Dependência de desenvolvimento presente em produção: {package}")
        return 1
    for package in (
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg",
        "psycopg-binary",
        "alembic",
        "pydantic-settings",
        "httpx",
        "cryptography",
        "redis",
    ):
        try:
            installed = version(package)
        except PackageNotFoundError:
            print(f"Dependência de produção ausente: {package}")
            return 1
        print(f"{package}=={installed}")
    print("Dependências de produção conferidas; ferramentas de teste ausentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
