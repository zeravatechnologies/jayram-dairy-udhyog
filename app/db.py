"""Database bootstrap: backups + Alembic migrations for file-backed SQLite."""
from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

BASELINE_REVISION = "0001_baseline"
# Bundled under this name in jayram_dairy.spec so the folder does not
# shadow the installed ``alembic`` Python package inside _MEIPASS.
FROZEN_ALEMBIC_SCRIPTS = "alembic_scripts"


def _project_root() -> Path:
    """Repo root (or PyInstaller _MEIPASS) that holds alembic.ini."""
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _alembic_script_location(root: Path) -> Path:
    import sys

    if getattr(sys, "frozen", False):
        return root / FROZEN_ALEMBIC_SCRIPTS
    return root / "alembic"


def alembic_config(db_url: str) -> Config:
    root = _project_root()
    ini_path = root / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(_alembic_script_location(root)))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _legacy_ensure_planning_note(engine) -> None:
    """Pre-Alembic DBs may lack planning_note; stamp alone does not add it."""
    inspector = inspect(engine)
    if "order_txn" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("order_txn")}
    if "planning_note" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE order_txn ADD COLUMN planning_note TEXT"))


def run_migrations(db_path: str) -> None:
    """Apply Alembic upgrades to a file-backed SQLite database.

    If the file already has application tables but no alembic_version
    (pre-migration installs), stamp to baseline then upgrade so data
    is preserved.
    """
    if db_path == ":memory:":
        return

    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    db_url = f"sqlite:///{db_path}"
    cfg = alembic_config(db_url)
    engine = create_engine(db_url, future=True)

    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        app_tables = table_names - {"alembic_version"}

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()

        if current is None and app_tables:
            _legacy_ensure_planning_note(engine)
            script = ScriptDirectory.from_config(cfg)
            head = script.get_current_head()
            command.stamp(cfg, head or BASELINE_REVISION)

        command.upgrade(cfg, "head")
    finally:
        engine.dispose()
