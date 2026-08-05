"""Structured activity logging.

Every sign-in and every data change gets one line here: timestamp, app
version, username, level, action, context. This is what the deployment
doc's "Send Diagnostic Report" flow and support triage (Section 7)
depend on — logged at the UI layer, right after each successful
service-layer call, so it naturally captures who was signed in
without threading a user through every service function signature.
"""
from datetime import datetime
import logging
import os

from app.utils.bs_date import NEPAL_TIMEZONE, to_bs_display

APP_VERSION = "0.5.4"
LOGGER_NAME = "jayram_dairy"

_logger = None


class NepalBsLogFormatter(logging.Formatter):
    """Render log timestamps as Nepal-local Bikram Sambat date and time."""

    def formatTime(self, record, datefmt=None):
        try:
            local_time = datetime.fromtimestamp(record.created, tz=NEPAL_TIMEZONE)
            offset = local_time.strftime("%z")
            readable_offset = f"{offset[:3]}:{offset[3:]}"
            return (
                f"{to_bs_display(local_time.date())} "
                f"{local_time:%H:%M:%S} {readable_offset}"
            )
        except Exception:
            # Packaged builds must still write a line if BS conversion fails.
            return datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")


def setup_logging(log_dir: str) -> logging.Logger:
    """Attach a FileHandler to the process-wide named logger."""
    global _logger
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        _logger = logger
        return logger

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "activity.log")

    logger.setLevel(logging.INFO)
    logger.propagate = False
    _close_handlers(logger)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = NepalBsLogFormatter(
        f"%(asctime)s | {APP_VERSION} | %(username)s | %(levelname)s | %(action)s | %(context)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    _logger = logger
    return logger


def close_logging():
    """Release the activity file so Windows can rotate or remove it."""
    global _logger
    logger = logging.getLogger(LOGGER_NAME)
    _close_handlers(logger)
    _logger = None


def _close_handlers(logger: logging.Logger):
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def log_action(username: str, action: str, context: str = "", level: str = "INFO"):
    """Write one structured line. Never raises — a logging failure
    should never block the user's actual work (deployment doc Section
    7.3: errors are handled gracefully, and logging itself is no
    exception to that).

    Uses the process-wide named logger so packaged (.exe) builds still
    write even if this module was imported under more than one identity.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        return
    # Alembic fileConfig can leave this logger disabled; re-enable for writes.
    logger.disabled = False
    extra = {"username": username or "unknown", "action": action, "context": context}
    try:
        if level == "ERROR":
            logger.error("", extra=extra)
        elif level == "WARNING":
            logger.warning("", extra=extra)
        else:
            logger.info("", extra=extra)
        for handler in logger.handlers:
            handler.flush()
    except Exception:
        pass  # logging must never crash the app


def to_bs_activity_timestamp(timestamp: str) -> str:
    """Convert timestamps from pre-BS log files while preserving new values."""
    for timestamp_format in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
        try:
            legacy_time = datetime.strptime(timestamp, timestamp_format)
            return (
                f"{to_bs_display(legacy_time.date())} "
                f"{legacy_time:%H:%M:%S} (legacy local time)"
            )
        except ValueError:
            continue
    return timestamp


def read_recent_log_lines(log_dir: str, limit: int = 50) -> list[str]:
    """Used by the Activity Log screen to show recent entries."""
    log_path = os.path.join(log_dir, "activity.log")
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [line.strip() for line in lines[-limit:]][::-1]  # most recent first
