"""Tests for balance calculation and the end-to-end milk collection flow.

Uses a real (in-memory) SQLite database rather than mocks — balance
calculation is exactly the kind of logic that looks right with mocks
and is wrong against a real database (e.g. Decimal vs float precision,
NULL handling on an empty vendor). Per architecture doc Section 5:
migrations get tested against real data shape, and this is that same
discipline applied to service-layer tests.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.models.vendor import Vendor
from app.services.milk_collection import record_milk_collection
from app.services.balance import get_vendor_balance


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


@pytest.fixture
def vendor(session):
    v = Vendor(name="Hari Thapa", phone="9841000000", pricing_mode="fat_based", default_rate=Decimal("9.42"))
    session.add(v)
    session.commit()
    return v


def test_balance_zero_with_no_transactions(session, vendor):
    assert get_vendor_balance(session, vendor.vendor_id) == Decimal("0")


def test_balance_after_one_unpaid_delivery(session, vendor):
    record_milk_collection(session, vendor.vendor_id, date(2026, 7, 14), Decimal("4.1"), Decimal("6.2"))
    balance = get_vendor_balance(session, vendor.vendor_id)
    assert balance == Decimal("239.46")


def test_balance_after_partial_payment_on_delivery(session, vendor):
    # Mirrors the "amount paid to vendor right now" field from the wireframe —
    # a payment linked directly to the delivery, for less than the full amount.
    record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("3.1"), Decimal("5.8"),
        amount_paid_now=Decimal("100"),
    )
    balance = get_vendor_balance(session, vendor.vendor_id)
    expected_amount = Decimal("3.1") * (Decimal("5.8") * Decimal("9.42")).quantize(Decimal("0.0001"))
    expected_amount = expected_amount.quantize(Decimal("0.01"))
    assert balance == (expected_amount - Decimal("100"))


def test_balance_across_multiple_deliveries_and_an_advance(session, vendor):
    record_milk_collection(session, vendor.vendor_id, date(2026, 7, 13), Decimal("4.4"), Decimal("6.0"))
    record_milk_collection(session, vendor.vendor_id, date(2026, 7, 14), Decimal("4.1"), Decimal("6.2"))

    from app.models.payment import Payment
    advance = Payment(party_type="vendor", party_id=vendor.vendor_id, linked_txn_id=None,
                       amount=Decimal("5000"), date=date(2026, 7, 12), status="paid", mode="advance")
    session.add(advance)
    session.commit()

    balance = get_vendor_balance(session, vendor.vendor_id)
    # Two deliveries (255.19 + 239.46 approx) minus a 5000 advance -> negative,
    # i.e. the vendor now owes the shop, which is a real, valid state.
    assert balance < 0


def test_balance_as_of_date_excludes_later_transactions(session, vendor):
    record_milk_collection(session, vendor.vendor_id, date(2026, 7, 13), Decimal("4.4"), Decimal("6.0"))
    record_milk_collection(session, vendor.vendor_id, date(2026, 7, 14), Decimal("4.1"), Decimal("6.2"))

    balance_on_13th = get_vendor_balance(session, vendor.vendor_id, as_of_date=date(2026, 7, 13))
    balance_on_14th = get_vendor_balance(session, vendor.vendor_id, as_of_date=date(2026, 7, 14))
    assert balance_on_13th < balance_on_14th


def test_record_milk_collection_rejects_zero_quantity(session, vendor):
    with pytest.raises(ValueError, match="greater than zero"):
        record_milk_collection(session, vendor.vendor_id, date(2026, 7, 14), Decimal("0"), Decimal("6.0"))


def test_record_milk_collection_rejects_unknown_vendor(session):
    with pytest.raises(ValueError, match="No such vendor"):
        record_milk_collection(session, 999, date(2026, 7, 14), Decimal("4.0"), Decimal("6.0"))
