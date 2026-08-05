"""UI audit logging — successful actions write; cancelled dialogs do not."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QDialog

from app.models.base import make_session_factory
from app.ui.production_screen import ProductionScreen
from app.ui.theme import APP_STYLESHEET
from app.utils.activity_log import close_logging, read_recent_log_lines, setup_logging


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    yield app


@pytest.fixture
def session():
    session_factory = make_session_factory(":memory:")
    database_session = session_factory()
    yield database_session
    database_session.close()


@pytest.fixture(autouse=True)
def release_log_file():
    yield
    close_logging()


def test_successful_product_create_writes_activity_line(qt_app, session, tmp_path, monkeypatch):
    close_logging()
    setup_logging(str(tmp_path))
    screen = ProductionScreen(session)
    screen.username = "dhiraj"

    class AcceptedDialog:
        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return {
                "name": "Paneer",
                "variant": None,
                "unit": "kg",
                "conversion_ratio": "5",
            }

    monkeypatch.setattr(
        "app.ui.production_screen.ProductDialog",
        lambda *args, **kwargs: AcceptedDialog(),
    )
    screen.open_add_product()

    lines = read_recent_log_lines(str(tmp_path))
    assert any("product.create" in line and "Paneer" in line for line in lines)
    assert any("dhiraj" in line for line in lines)
    screen.close()


def test_cancelled_product_dialog_does_not_write_activity_line(
    qt_app, session, tmp_path, monkeypatch
):
    close_logging()
    setup_logging(str(tmp_path))
    screen = ProductionScreen(session)
    screen.username = "dhiraj"

    class CancelledDialog:
        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "app.ui.production_screen.ProductDialog",
        lambda *args, **kwargs: CancelledDialog(),
    )
    screen.open_add_product()

    assert read_recent_log_lines(str(tmp_path)) == []
    screen.close()
