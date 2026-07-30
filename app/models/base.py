"""Base SQLAlchemy declarative setup and session factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.db import run_migrations
from app.services.backup import backup_database

Base = declarative_base()


def make_session_factory(db_path: str, *, backup_dir: str | None = None):
    """Create an engine + session factory pointed at a specific SQLite file.

    File-backed DBs: backup (if backup_dir set), then Alembic upgrade.
    In-memory DBs (tests): create_all only — Alembic is not used.
    """
    import app.models  # noqa: F401 — register tables on Base.metadata

    if db_path == ":memory:":
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, future=True)

    if backup_dir:
        backup_database(db_path, backup_dir, force=True)

    run_migrations(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    return sessionmaker(bind=engine, future=True)
