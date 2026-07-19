"""Base SQLAlchemy declarative setup and session factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def make_session_factory(db_path: str):
    """Create an engine + session factory pointed at a specific SQLite file.

    Kept as a factory (not a module-level singleton) so tests can point
    at an in-memory or temp database instead of the real app data file.
    """
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)
