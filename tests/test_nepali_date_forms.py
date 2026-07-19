import os
from datetime import date
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication
from sqlalchemy import select

from app.models.base import make_session_factory
from app.models.order import OrderTransaction
from app.models.payment import Payment
from app.models.production_batch import ProductionBatch
from app.models.transaction import RawMaterialTransaction
from app.services.customers import create_customer
from app.services.milk_collection import record_milk_collection
from app.services.products import create_product
from app.services.vendors import create_vendor
from app.ui.orders_screen import OrdersScreen
from app.ui.payments_screen import PaymentsScreen
from app.ui.production_screen import ProductionScreen
from app.ui.vendor_screen import VendorScreen

SELECTED_DATE = date(2026, 4, 14)
LATER_DATE = date(2026, 4, 20)


@pytest.fixture(scope="module")
def qt_app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def session():
    session_factory = make_session_factory(":memory:")
    database_session = session_factory()
    yield database_session
    database_session.close()


def test_vendor_form_persists_selected_bs_date(qt_app, session):
    create_vendor(
        session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58")
    )
    screen = VendorScreen(session)
    screen.collection_date_input.set_ad_date(SELECTED_DATE)
    screen.qty_input.setText("4")

    screen.save_entry()

    transaction = session.execute(select(RawMaterialTransaction)).scalar_one()
    assert transaction.date == SELECTED_DATE
    screen.close()


def test_order_form_persists_selected_order_and_delivery_dates(qt_app, session):
    create_customer(session, "Hotel Annapurna", "111", "addr")
    product = create_product(session, "Khuwa", unit="kg")
    product.current_stock = Decimal("10")
    session.commit()
    screen = OrdersScreen(session)
    screen.order_date_input.set_ad_date(SELECTED_DATE)
    screen.delivery_date_input.set_ad_date(LATER_DATE)
    screen.qty_input.setText("2")
    screen.rate_input.setText("380")

    screen.save_order()

    order = session.execute(select(OrderTransaction)).scalar_one()
    assert order.order_date == SELECTED_DATE
    assert order.delivery_date == LATER_DATE
    screen.close()


def test_payment_form_persists_selected_bs_date(qt_app, session):
    create_vendor(
        session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58")
    )
    screen = PaymentsScreen(session)
    screen.payment_date_input.set_ad_date(SELECTED_DATE)
    screen.amount_input.setText("500")

    screen.save_payment()

    payment = session.execute(select(Payment)).scalar_one()
    assert payment.date == SELECTED_DATE
    screen.close()


def test_production_form_persists_selected_production_and_expiry_dates(
    qt_app, session
):
    vendor = create_vendor(
        session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58")
    )
    record_milk_collection(
        session, vendor.vendor_id, SELECTED_DATE, Decimal("20")
    )
    create_product(session, "Khuwa", unit="kg")
    screen = ProductionScreen(session)
    screen.production_date_input.set_ad_date(SELECTED_DATE)
    screen.expiry_date_input.set_ad_date(LATER_DATE)
    screen.consumed_input.setText("10")
    screen.output_input.setText("2")

    screen.save_batch()

    batch = session.execute(select(ProductionBatch)).scalar_one()
    assert batch.date == SELECTED_DATE
    assert batch.expiry_date == LATER_DATE
    screen.close()
