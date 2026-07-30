"""Tests for app.services.dashboard."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.services.vendors import create_vendor
from app.services.customers import create_customer
from app.services.products import create_product
from app.services.milk_collection import record_milk_collection
from app.services.orders import create_order
from app.services.payments import record_payment
from app.services.dashboard import (
    get_today_milk_total, get_today_milk_by_session,
    get_total_vendor_payable, get_total_customer_due,
    get_low_stock_products,
)
from app.services.production import get_pool_available
from app.utils.bs_date import today_in_nepal


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


def test_today_milk_total_only_counts_today(session):
    v = create_vendor(session, "Hari Thapa", "1", "a", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, today_in_nepal(), Decimal("10"))
    record_milk_collection(session, v.vendor_id, date(2020, 1, 1), Decimal("999"))  # not today
    assert get_today_milk_total(session) == Decimal("10")


def test_today_milk_includes_morning_and_evening(session):
    v = create_vendor(session, "Hari Thapa", "1", "a", "flat_rate", Decimal("58"))
    today = today_in_nepal()
    record_milk_collection(
        session, v.vendor_id, today, Decimal("10"), session_label="morning",
    )
    record_milk_collection(
        session, v.vendor_id, today, Decimal("5"), session_label="evening",
    )
    assert get_today_milk_total(session, today=today) == Decimal("15")
    by_session = get_today_milk_by_session(session, today=today)
    assert by_session["morning"] == Decimal("10")
    assert by_session["evening"] == Decimal("5")


def test_evening_on_other_date_in_pool_not_in_today(session):
    v = create_vendor(session, "Hari Thapa", "1", "a", "flat_rate", Decimal("58"))
    today = today_in_nepal()
    record_milk_collection(
        session, v.vendor_id, today, Decimal("10"), session_label="morning",
    )
    record_milk_collection(
        session, v.vendor_id, date(2020, 1, 1), Decimal("7"), session_label="evening",
    )
    assert get_today_milk_total(session, today=today) == Decimal("10")
    assert get_pool_available(session) == Decimal("17")


def test_total_vendor_payable_sums_only_positive_balances(session):
    v1 = create_vendor(session, "Hari Thapa", "1", "a", "flat_rate", Decimal("58"))
    v2 = create_vendor(session, "Ram Bahadur", "2", "b", "flat_rate", Decimal("55"))
    record_milk_collection(session, v1.vendor_id, date(2026, 7, 14), Decimal("10"))  # 580 owed
    record_milk_collection(session, v2.vendor_id, date(2026, 7, 14), Decimal("10"))  # 550 owed
    record_payment(session, "vendor", v2.vendor_id, Decimal("1000"), date(2026, 7, 14))  # v2 now overpaid (negative)

    total = get_total_vendor_payable(session)
    assert total == Decimal("580")  # v2's negative balance does NOT offset v1's payable


def test_total_customer_due_sums_only_positive_balances(session):
    p = create_product(session, "Khuwa", unit="kg")
    p.current_stock = Decimal("100")
    session.commit()
    c = create_customer(session, "Hotel Annapurna", "1", "a")
    create_order(session, c.customer_id, p.product_id, date(2026, 7, 14), Decimal("5"), Decimal("380"))
    assert get_total_customer_due(session) == Decimal("1900.00")


def test_low_stock_products_below_threshold(session):
    p1 = create_product(session, "Khuwa", unit="kg")
    p1.current_stock = Decimal("2")
    p2 = create_product(session, "Paneer", unit="kg")
    p2.current_stock = Decimal("20")
    session.commit()

    low = get_low_stock_products(session, threshold=Decimal("5"))
    names = [p.name for p in low]
    assert "Khuwa" in names
    assert "Paneer" not in names
