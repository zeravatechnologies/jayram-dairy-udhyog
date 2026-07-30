"""Tests for local database backup retention and daily skip."""
import os
from datetime import datetime
from pathlib import Path

from app.services.backup import backup_database, DEFAULT_KEEP


def test_backup_noop_when_db_missing(tmp_path):
    db = tmp_path / "missing.db"
    backup_dir = tmp_path / "backups"
    assert backup_database(str(db), str(backup_dir)) is None
    assert not backup_dir.exists() or list(backup_dir.iterdir()) == []


def test_backup_noop_for_memory():
    assert backup_database(":memory:", "/tmp/unused") is None


def test_backup_creates_copy(tmp_path):
    db = tmp_path / "jayram_dairy.db"
    db.write_bytes(b"sqlite-bytes")
    backup_dir = tmp_path / "backups"

    dest = backup_database(str(db), str(backup_dir), force=True)

    assert dest is not None
    assert Path(dest).is_file()
    assert Path(dest).read_bytes() == b"sqlite-bytes"
    assert Path(dest).name.startswith("jayram_dairy_")
    assert Path(dest).name.endswith(".db")


def test_backup_skips_when_same_day_exists_and_not_forced(tmp_path):
    db = tmp_path / "jayram_dairy.db"
    db.write_bytes(b"v1")
    backup_dir = tmp_path / "backups"
    first = backup_database(str(db), str(backup_dir), force=True)
    assert first is not None

    db.write_bytes(b"v2")
    second = backup_database(str(db), str(backup_dir), force=False)
    assert second is None
    assert list(backup_dir.glob("*.db")) == [Path(first)]


def test_backup_force_creates_another_same_day(tmp_path):
    db = tmp_path / "jayram_dairy.db"
    db.write_bytes(b"v1")
    backup_dir = tmp_path / "backups"
    first = backup_database(str(db), str(backup_dir), force=True)
    second = backup_database(str(db), str(backup_dir), force=True)
    assert first is not None and second is not None
    assert first != second
    assert len(list(backup_dir.glob("*.db"))) == 2


def test_backup_retention_keeps_only_last_n(tmp_path):
    db = tmp_path / "jayram_dairy.db"
    db.write_bytes(b"data")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed older-named files so prune has something to drop.
    for i in range(DEFAULT_KEEP + 3):
        stamp = f"20200101_{i:06d}"
        (backup_dir / f"jayram_dairy_{stamp}.db").write_bytes(b"old")

    backup_database(str(db), str(backup_dir), force=True, keep=DEFAULT_KEEP)

    remaining = sorted(p.name for p in backup_dir.glob("*.db"))
    assert len(remaining) == DEFAULT_KEEP
    # Newest name sorts last among YYYYMMDD_HHMMSS; today's stamp is newest.
    today = datetime.now().strftime("%Y%m%d")
    assert remaining[-1].startswith(f"jayram_dairy_{today}_")
