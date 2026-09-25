from sqlalchemy.engine import Connection


def prepare_version_table(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS public.alembic_version "
        "(version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
    )
    connection.exec_driver_sql(
        "ALTER TABLE public.alembic_version "
        "ALTER COLUMN version_num TYPE VARCHAR(128)"
    )
