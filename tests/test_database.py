from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Workspace


def test_workspace_model_can_be_persisted() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workspace = Workspace(
            name="Nexyra Demo",
            slug="nexyra-demo",
            segment="generic",
        )
        session.add(workspace)
        session.commit()

        assert workspace.id is not None
        assert workspace.public_id.startswith("WS-")

        saved = session.scalar(
            select(Workspace).where(
                Workspace.slug == "nexyra-demo"
            )
        )

        assert saved is not None
        assert saved.name == "Nexyra Demo"
        assert saved.segment == "generic"
        assert saved.active is True


def test_same_workspace_slug_is_unique() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    first = Workspace(
        name="Empresa A",
        slug="empresa",
        segment="retail",
    )
    second = Workspace(
        name="Empresa B",
        slug="empresa",
        segment="services",
    )

    with Session(engine) as session:
        session.add(first)
        session.commit()

        session.add(second)

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError(
                "O banco deveria impedir slugs duplicados."
            )
