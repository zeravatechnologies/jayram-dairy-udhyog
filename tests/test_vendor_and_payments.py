"""Tests for vendor CRUD, manual rate override, and per-transaction
payment status — the additions made after the first real run-through.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.services.vendors import create_vendor, update_vendor, delete_vendor, list_vendors
from app.services.milk_collection import record_milk_collection
from app.services.payments import get_amount_paid_for_txn, get_txn_status


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


def test_create_and_list_vendor(session):
    create_vendor(session, "Sita Devi", "9817000004", "Mirchaiya", "fat_based", Decimal("9.0"))
    vendors = list_vendors(session)
    assert len(vendors) == 1
    assert vendors[0].name == "Sita Devi"


def test_create_vendor_requires_name(session):
    with pytest.raises(ValueError, match="name is required"):
        create_vendor(session, "  ", "123", "addr", "fat_based", Decimal("9.0"))


def test_update_vendor_rate(session):
    v = create_vendor(session, "Sita Devi", "9817000004", "Mirchaiya", "fat_based", Decimal("9.0"))
    update_vendor(session, v.vendor_id, default_rate=Decimal("9.5"))
    assert v.default_rate == Decimal("9.5")


def test_delete_vendor_blocked_if_has_history(session):
    v = create_vendor(session, "Sita Devi", "9817000004", "Mirchaiya", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("4.0"))
    with pytest.raises(ValueError, match="existing delivery history"):
        delete_vendor(session, v.vendor_id)


def test_delete_vendor_allowed_with_no_history(session):
    v = create_vendor(session, "New Vendor", "111", "addr", "flat_rate", Decimal("58"))
    delete_vendor(session, v.vendor_id)  # should not raise
    assert list_vendors(session) == []


def test_manual_rate_override_ignores_computed_fat_price(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "fat_based", Decimal("9.42"))
    txn = record_milk_collection(
        session, v.vendor_id, date(2026, 7, 14), Decimal("4.0"), Decimal("6.0"),
        manual_rate=Decimal("70.00"),  # negotiated one-off price
    )
    assert txn.rate_applied == Decimal("70.00")
    assert txn.amount == Decimal("280.00")  # not the fat-based 4.0 * 6.0 * 9.42


def test_payment_status_pending_partial_paid(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    txn = record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("4.0"))  # amount = 232.00

    paid = get_amount_paid_for_txn(session, txn.txn_id, party_type="vendor")
    assert get_txn_status(txn.amount, paid) == "pending"

    txn2 = record_milk_collection(
        session, v.vendor_id, date(2026, 7, 14), Decimal("4.0"), amount_paid_now=Decimal("100")
    )
    paid2 = get_amount_paid_for_txn(session, txn2.txn_id, party_type="vendor")
    assert get_txn_status(txn2.amount, paid2) == "partial"

    txn3 = record_milk_collection(
        session, v.vendor_id, date(2026, 7, 14), Decimal("4.0"), amount_paid_now=Decimal("232.00")
    )
    paid3 = get_amount_paid_for_txn(session, txn3.txn_id, party_type="vendor")
    assert get_txn_status(txn3.amount, paid3) == "paid"
