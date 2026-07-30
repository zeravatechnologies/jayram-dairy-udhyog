"""Tests for app.services.payments — the standalone record_payment used
by the Payments screen, and the recent-payments listing.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.services.vendors import create_vendor
from app.services.customers import create_customer
from app.services.payments import (
    delete_payment,
    list_recent_payments,
    record_payment,
    update_payment,
)
from app.services.balance import get_vendor_balance, get_customer_balance


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


def test_record_payment_for_vendor_reduces_balance(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_payment(session, "vendor", v.vendor_id, Decimal("500"), date(2026, 7, 14), mode="advance")
    assert get_vendor_balance(session, v.vendor_id) == Decimal("-500")  # vendor now owes shop


def test_record_payment_for_customer_reduces_balance(session):
    c = create_customer(session, "Hotel Annapurna", "111", "addr")
    record_payment(session, "customer", c.customer_id, Decimal("200"), date(2026, 7, 14))
    assert get_customer_balance(session, c.customer_id) == Decimal("-200")


def test_record_payment_rejects_bad_party_type(session):
    with pytest.raises(ValueError, match="party_type must be"):
        record_payment(session, "supplier", 1, Decimal("100"), date(2026, 7, 14))


def test_record_payment_rejects_unknown_party(session):
    with pytest.raises(ValueError, match="No such vendor"):
        record_payment(session, "vendor", 999, Decimal("100"), date(2026, 7, 14))


def test_record_payment_rejects_zero_amount(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    with pytest.raises(ValueError, match="greater than zero"):
        record_payment(session, "vendor", v.vendor_id, Decimal("0"), date(2026, 7, 14))


def test_list_recent_payments_resolves_party_names(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    c = create_customer(session, "Hotel Annapurna", "111", "addr")
    record_payment(session, "vendor", v.vendor_id, Decimal("500"), date(2026, 7, 13))
    record_payment(session, "customer", c.customer_id, Decimal("200"), date(2026, 7, 14))

    recent = list_recent_payments(session)
    names = [name for _, name in recent]
    assert "Hari Thapa" in names
    assert "Hotel Annapurna" in names
    # most recent first
    assert recent[0][1] == "Hotel Annapurna"


def test_recent_payments_sort_across_bs_new_year(session):
    vendor = create_vendor(
        session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58")
    )
    record_payment(
        session, "vendor", vendor.vendor_id, Decimal("100"), date(2026, 4, 13)
    )
    record_payment(
        session, "vendor", vendor.vendor_id, Decimal("200"), date(2026, 4, 14)
    )

    recent = list_recent_payments(session)

    assert [payment.amount for payment, _ in recent] == [
        Decimal("200"),
        Decimal("100"),
    ]


def test_update_payment_changes_balance(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    payment = record_payment(
        session, "vendor", v.vendor_id, Decimal("500"), date(2026, 7, 14), mode="advance"
    )
    assert get_vendor_balance(session, v.vendor_id) == Decimal("-500")

    update_payment(
        session, payment.payment_id, Decimal("200"), date(2026, 7, 14), mode="partial"
    )
    assert get_vendor_balance(session, v.vendor_id) == Decimal("-200")
    assert payment.amount == Decimal("200")
    assert payment.mode == "partial"


def test_delete_payment_restores_balance(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    payment = record_payment(
        session, "vendor", v.vendor_id, Decimal("500"), date(2026, 7, 14)
    )
    delete_payment(session, payment.payment_id)
    assert get_vendor_balance(session, v.vendor_id) == Decimal("0")
    assert list_recent_payments(session) == []
