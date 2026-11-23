"""Utilidades de base de datos para pruebas (SQLite, sin servidor PostgreSQL)."""

from sqlalchemy import Engine, StaticPool, create_engine, event

IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def make_sqlite_engine(url: str = IN_MEMORY_URL) -> Engine:
    if url == IN_MEMORY_URL:
        # Una única conexión compartida: la base en memoria es visible desde
        # cualquier hilo (TestClient ejecuta los endpoints en otro hilo).
        engine = create_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:
        # SQLite no aplica claves foráneas salvo que se active explícitamente.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine
