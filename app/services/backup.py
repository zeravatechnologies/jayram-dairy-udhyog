"""Local SQLite database backups for safe upgrades and recovery."""
from __future__ import annotations

import os
import shutil
from datetime import date, datetime
from pathlib import Path

DEFAULT_KEEP = 10
BACKUP_PREFIX = "jayram_dairy_"
BACKUP_SUFFIX = ".db"


def backup_database(
    db_path: str,
    backup_dir: str,
    *,
    keep: int = DEFAULT_KEEP,
    force: bool = True,
) -> str | None:
    """Copy the live DB into backup_dir.

    Returns the backup file path, or None if there was nothing to copy
    (missing DB) or if force is False and a same-calendar-day backup
    already exists.
    """
    if not db_path or db_path == ":memory:":
        return None
    if not os.path.isfile(db_path):
        return None

    os.makedirs(backup_dir, exist_ok=True)

    if not force and _has_backup_for_today(backup_dir):
        return None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}")
    shutil.copy2(db_path, dest)
    _prune_old_backups(backup_dir, keep=keep)
    return dest


def _backup_files(backup_dir: str) -> list[Path]:
    root = Path(backup_dir)
    if not root.is_dir():
        return []
    files = [
        p for p in root.iterdir()
        if p.is_file() and p.name.startswith(BACKUP_PREFIX) and p.name.endswith(BACKUP_SUFFIX)
    ]
    return sorted(files, key=lambda p: p.name)


def _has_backup_for_today(backup_dir: str) -> bool:
    today = date.today().strftime("%Y%m%d")
    prefix = f"{BACKUP_PREFIX}{today}_"
    return any(p.name.startswith(prefix) for p in _backup_files(backup_dir))


def _prune_old_backups(backup_dir: str, *, keep: int) -> None:
    if keep < 1:
        keep = 1
    files = _backup_files(backup_dir)
    excess = files[:-keep] if len(files) > keep else []
    for path in excess:
        path.unlink(missing_ok=True)
