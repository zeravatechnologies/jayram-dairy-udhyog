"""Tests for app.utils.activity_log — the audit trail the deployment
doc's support/diagnostic flow depends on.
"""
import pytest

from app.utils.activity_log import (
    close_logging,
    log_action,
    read_recent_log_lines,
    setup_logging,
    to_bs_activity_timestamp,
)
import app.utils.activity_log as activity_log_module


@pytest.fixture(autouse=True)
def release_log_file():
    yield
    close_logging()


def test_log_action_writes_a_readable_line(tmp_path):
    close_logging()
    setup_logging(str(tmp_path))
    log_action("jayram.owner", "vendor.create", "name=Hari Thapa")

    lines = read_recent_log_lines(str(tmp_path))
    assert len(lines) == 1
    assert "jayram.owner" in lines[0]
    assert "vendor.create" in lines[0]
    assert "Hari Thapa" in lines[0]
    assert "0.5.4" in lines[0]
    timestamp = lines[0].split(" | ", 1)[0]
    assert "+05:45" in timestamp
    assert any(digit in timestamp for digit in "०१२३४५६७८९")
    close_logging()


def test_log_action_uses_named_logger_when_module_global_is_cleared(tmp_path):
    """Packaged apps can lose the module _logger; named logger must still write."""
    close_logging()
    setup_logging(str(tmp_path))
    activity_log_module._logger = None
    log_action("dhiraj", "auth.login", "signed in")

    lines = read_recent_log_lines(str(tmp_path))
    assert len(lines) == 1
    assert "auth.login" in lines[0]
    assert "dhiraj" in lines[0]
    close_logging()


def test_log_action_still_writes_after_alembic_disables_logger(tmp_path):
    """Alembic fileConfig(disable_existing_loggers=True) must not mute audits."""
    import logging

    close_logging()
    setup_logging(str(tmp_path))
    logging.getLogger(activity_log_module.LOGGER_NAME).disabled = True
    log_action("dhiraj", "product.create", "Paneer")

    lines = read_recent_log_lines(str(tmp_path))
    assert any("product.create" in line for line in lines)
    close_logging()


def test_read_recent_log_lines_most_recent_first(tmp_path):
    close_logging()
    setup_logging(str(tmp_path))
    log_action("jayram.owner", "action.one")
    log_action("jayram.owner", "action.two")

    lines = read_recent_log_lines(str(tmp_path))
    assert "action.two" in lines[0]
    assert "action.one" in lines[1]
    close_logging()


def test_read_recent_log_lines_empty_when_no_file_yet(tmp_path):
    assert read_recent_log_lines(str(tmp_path)) == []


def test_log_action_before_setup_does_not_crash():
    close_logging()
    log_action("someone", "some.action")  # should silently no-op, not raise


def test_legacy_gregorian_timestamp_is_displayed_as_bs():
    converted = to_bs_activity_timestamp("2026-07-18 23:04:08,123")

    assert converted.startswith("श्रावण २, २०८३ 23:04:08")
    assert "2026-07-18" not in converted
