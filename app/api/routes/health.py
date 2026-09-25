from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.db.runtime import database_backend

router = APIRouter(
    prefix="/health",
    tags=["system"],
)


@router.get("")
def health() -> dict[str, str | bool]:
    settings = get_settings()

    return {
        "ok": True,
        "product": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "deployment_mode": settings.deployment_mode,
    }


@router.get("/ready")
def readiness(db: Annotated[Session, Depends(get_db)]) -> dict[str, str | bool]:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados indisponível.",
        ) from exc

    return {
        "ok": True,
        "database": database_backend(settings.database_url),
        "deployment_mode": settings.deployment_mode,
    }
