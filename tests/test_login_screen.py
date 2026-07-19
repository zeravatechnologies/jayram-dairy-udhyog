"""Visual-style regression tests for the login screen."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QLabel

from app.models.base import make_session_factory
from app.services.auth import create_user
from app.ui.login_screen import LoginScreen
from app.ui.theme import APP_STYLESHEET


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


def test_login_uses_scoped_application_theme(qt_app, session):
    create_user(session, "owner", "secret123")

    screen = LoginScreen(session)

    assert screen.objectName() == "loginRoot"
    assert "QWidget#loginRoot" in qt_app.styleSheet()
    assert "QWidget#card" in qt_app.styleSheet()


def test_login_form_has_visible_labels_and_accessible_fields(qt_app, session):
    create_user(session, "owner", "secret123")

    screen = LoginScreen(session)
    field_labels = screen.findChildren(QLabel, "fieldLabel")

    assert [label.text() for label in field_labels] == ["Username", "Password"]
    assert screen.username_input.accessibleName() == "Username"
    assert screen.password_input.accessibleName() == "Password"
