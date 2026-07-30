"""Widget-level checks for the shared UI system."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.models.base import make_session_factory
from app.ui.main_window import MainWindow
from app.ui.orders_screen import OrdersScreen
from app.ui.payments_screen import PaymentsScreen
from app.ui.production_screen import ProductionScreen
from app.ui.theme import APP_STYLESHEET
from app.ui.vendor_screen import VendorScreen


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


def test_main_window_has_readable_navigation_and_active_state(qt_app, session, tmp_path):
    window = MainWindow(session, "owner", str(tmp_path))

    assert window.minimumWidth() == 800
    assert window.nav_buttons["home"].property("active") == "true"
    assert "Home" in window.nav_buttons["home"].text()

    window.show_screen("production")
    assert window.nav_buttons["production"].property("active") == "true"
    assert window.stack.currentWidget().widget().layout().itemAt(0).widget() is (
        window.production_screen
    )
    window.close()


def test_all_pages_support_the_minimum_window_size(qt_app, session, tmp_path):
    window = MainWindow(session, "owner", str(tmp_path))
    window.resize(800, 600)
    window.show()
    qt_app.processEvents()

    assert window.sidebar.width() == 170
    screens = {
        "home": window.dashboard_screen,
        "vendor": window.vendor_screen,
        "production": window.production_screen,
        "orders": window.orders_screen,
        "payments": window.payments_screen,
        "log": window.activity_log_screen,
    }
    for key, screen in screens.items():
        window.show_screen(key)
        qt_app.processEvents()
        container = window.page_containers[screen]

        assert window.stack.currentWidget() is container
        assert container.horizontalScrollBarPolicy() == (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert screen.width() <= container.viewport().width()

    window.close()


def test_transaction_amount_fields_reject_letters(qt_app, session):
    screens_and_fields = [
        (VendorScreen(session), "qty_input"),
        (OrdersScreen(session), "qty_input"),
        (ProductionScreen(session), "consumed_input"),
        (PaymentsScreen(session), "amount_input"),
    ]

    for screen, field_name in screens_and_fields:
        field = getattr(screen, field_name)
        field.setText("letters")
        assert not field.hasAcceptableInput()
        screen.close()


def test_empty_states_are_visible_for_fresh_database(qt_app, session):
    vendor_screen = VendorScreen(session)
    orders_screen = OrdersScreen(session)
    production_screen = ProductionScreen(session)
    payments_screen = PaymentsScreen(session)

    assert not vendor_screen.empty_label.isHidden()
    assert not orders_screen.empty_label.isHidden()
    assert not production_screen.stock_empty_label.isHidden()
    assert not payments_screen.empty_label.isHidden()

    for screen in (vendor_screen, orders_screen, production_screen, payments_screen):
        screen.close()
