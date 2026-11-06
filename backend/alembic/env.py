"""Entorno de ejecución de Alembic para DermAI."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    """URL explícita en la configuración (p. ej. pruebas) o DATABASE_URL del entorno."""
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL no está configurada. Copia .env.example como .env "
            "en la raíz del proyecto y ajusta la URL de PostgreSQL."
        )
    return url


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base de datos (`alembic upgrade head --sql`)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_with_connection(connection)
        return

    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        _run_with_connection(conn)


def _run_with_connection(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
