"""Tests for Alembic bootstrap and legacy DB stamping."""
import os
from decimal import Decimal

from sqlalchemy import create_engine, inspect, text

from app.db import BASELINE_REVISION, run_migrations
from app.models import Vendor
from app.models.base import Base, make_session_factory


def test_run_migrations_creates_schema_on_new_file(tmp_path):
    db_path = str(tmp_path / "fresh.db")
    run_migrations(db_path)

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        tables = set(inspect(engine).get_table_names())
        order_cols = {c["name"] for c in inspect(engine).get_columns("order_txn")}
    finally:
        engine.dispose()

    assert "vendor" in tables
    assert "order_txn" in tables
    assert "user" in tables
    assert "alembic_version" in tables
    assert "planning_note" in order_cols


def test_make_session_factory_file_db_round_trip(tmp_path):
    db_path = str(tmp_path / "app.db")
    backup_dir = str(tmp_path / "backups")
    Session = make_session_factory(db_path, backup_dir=backup_dir)
    session = Session()
    session.add(Vendor(name="Test Vendor", pricing_mode="flat_rate", default_rate=Decimal("50")))
    session.commit()
    vendor_id = session.execute(text("SELECT vendor_id FROM vendor")).scalar()
    session.close()

    Session2 = make_session_factory(db_path, backup_dir=backup_dir)
    session2 = Session2()
    name = session2.execute(text("SELECT name FROM vendor WHERE vendor_id = :id"), {"id": vendor_id}).scalar()
    session2.close()
    assert name == "Test Vendor"
    assert os.path.isdir(backup_dir)
    assert any(name.endswith(".db") for name in os.listdir(backup_dir))


def test_legacy_create_all_db_is_stamped_without_data_loss(tmp_path):
    """Pre-Alembic DB (create_all, no alembic_version) must stamp and keep rows."""
    db_path = str(tmp_path / "legacy.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    import app.models  # noqa: F401
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO vendor (name, pricing_mode, default_rate, branch_id) "
                "VALUES ('Legacy Vendor', 'flat_rate', 40, 1)"
            )
        )
        # Simulate older schema missing planning_note
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(order_txn)")).fetchall()}
        if "planning_note" in cols:
            # recreate order_txn without planning_note is heavy; drop column not in sqlite.
            # Instead verify stamp path with full create_all schema — still no alembic_version.
            pass
    engine.dispose()

    assert "alembic_version" not in inspect(create_engine(f"sqlite:///{db_path}")).get_table_names()

    run_migrations(db_path)

    engine2 = create_engine(f"sqlite:///{db_path}", future=True)
    tables = set(inspect(engine2).get_table_names())
    with engine2.connect() as conn:
        name = conn.execute(text("SELECT name FROM vendor")).scalar()
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine2.dispose()

    assert name == "Legacy Vendor"
    assert "alembic_version" in tables
    assert rev == BASELINE_REVISION


def test_legacy_db_missing_planning_note_gets_column(tmp_path):
    db_path = str(tmp_path / "old_orders.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE vendor (vendor_id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                          "phone TEXT, address TEXT, pricing_mode TEXT NOT NULL, "
                          "default_rate NUMERIC NOT NULL, branch_id INTEGER NOT NULL)"))
        conn.execute(text("CREATE TABLE product (product_id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                          "variant TEXT, unit TEXT NOT NULL, current_stock NUMERIC NOT NULL, "
                          "conversion_ratio NUMERIC)"))
        conn.execute(text("CREATE TABLE customer (customer_id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                          "phone TEXT, address TEXT, type_tag TEXT, credit_days INTEGER, "
                          "branch_id INTEGER NOT NULL)"))
        conn.execute(text(
            "CREATE TABLE order_txn ("
            "order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, product_id INTEGER NOT NULL, "
            "order_date DATE NOT NULL, delivery_date DATE, quantity NUMERIC NOT NULL, "
            "rate NUMERIC NOT NULL, amount NUMERIC NOT NULL, status TEXT NOT NULL, "
            "created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO vendor (name, pricing_mode, default_rate, branch_id) "
            "VALUES ('V', 'flat_rate', 1, 1)"
        ))
    engine.dispose()

    run_migrations(db_path)

    engine2 = create_engine(f"sqlite:///{db_path}", future=True)
    cols = {c["name"] for c in inspect(engine2).get_columns("order_txn")}
    with engine2.connect() as conn:
        name = conn.execute(text("SELECT name FROM vendor")).scalar()
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine2.dispose()

    assert "planning_note" in cols
    assert name == "V"
    assert rev == BASELINE_REVISION


def test_memory_factory_still_works_without_alembic():
    from sqlalchemy import select

    Session = make_session_factory(":memory:")
    session = Session()
    session.add(Vendor(name="Mem", pricing_mode="fat_based", default_rate=Decimal("1")))
    session.commit()
    assert len(list(session.execute(select(Vendor)).scalars())) == 1
    session.close()
