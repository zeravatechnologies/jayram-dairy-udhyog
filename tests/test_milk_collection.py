"""Tests for milk collection create/update/delete and pool guards."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.services.balance import get_vendor_balance
from app.services.milk_collection import (
    delete_milk_collection,
    record_milk_collection,
    update_milk_collection,
)
from app.services.payments import get_amount_paid_for_txn
from app.services.production import get_pool_available, save_production_batch
from app.services.products import create_product
from app.services.vendors import create_vendor


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


@pytest.fixture
def vendor(session):
    return create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))


def test_update_qty_recalculates_amount_and_balance(session, vendor):
    txn = record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("42")
    )
    assert txn.amount == Decimal("2436.00")  # 42 * 58
    assert get_vendor_balance(session, vendor.vendor_id) == Decimal("2436.00")

    updated = update_milk_collection(
        session,
        txn.txn_id,
        date(2026, 7, 14),
        Decimal("24"),
        session_label=txn.session,
    )
    assert updated.quantity_l == Decimal("24")
    assert updated.amount == Decimal("1392.00")  # 24 * 58
    assert get_vendor_balance(session, vendor.vendor_id) == Decimal("1392.00")
    assert get_pool_available(session) == Decimal("24")


def test_update_rejects_qty_reduction_when_pool_insufficient(session, vendor):
    txn = record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("40")
    )
    product = create_product(session, "Khuwa", unit="kg")
    save_production_batch(
        session, date(2026, 7, 14), Decimal("30"), product.product_id, Decimal("6")
    )
    assert get_pool_available(session) == Decimal("10")

    with pytest.raises(ValueError, match="raw milk pool short"):
        update_milk_collection(
            session,
            txn.txn_id,
            date(2026, 7, 14),
            Decimal("20"),  # reduction of 20 > 10 available
            session_label=txn.session,
        )


def test_update_syncs_linked_paid_now_payment(session, vendor):
    txn = record_milk_collection(
        session,
        vendor.vendor_id,
        date(2026, 7, 14),
        Decimal("10"),
        amount_paid_now=Decimal("100"),
    )
    assert get_amount_paid_for_txn(session, txn.txn_id, "vendor") == Decimal("100")

    update_milk_collection(
        session,
        txn.txn_id,
        date(2026, 7, 14),
        Decimal("10"),
        session_label=txn.session,
        amount_paid_now=Decimal("200"),
    )
    assert get_amount_paid_for_txn(session, txn.txn_id, "vendor") == Decimal("200")
    assert get_vendor_balance(session, vendor.vendor_id) == Decimal("380.00")  # 580 - 200

    update_milk_collection(
        session,
        txn.txn_id,
        date(2026, 7, 14),
        Decimal("10"),
        session_label=txn.session,
        amount_paid_now=None,
    )
    assert get_amount_paid_for_txn(session, txn.txn_id, "vendor") == Decimal("0")


def test_delete_milk_collection_removes_payment_and_restores_pool(session, vendor):
    txn = record_milk_collection(
        session,
        vendor.vendor_id,
        date(2026, 7, 14),
        Decimal("10"),
        amount_paid_now=Decimal("50"),
    )
    delete_milk_collection(session, txn.txn_id)
    assert get_pool_available(session) == Decimal("0")
    assert get_vendor_balance(session, vendor.vendor_id) == Decimal("0")


def test_delete_rejected_when_pool_insufficient(session, vendor):
    txn = record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("40")
    )
    product = create_product(session, "Khuwa", unit="kg")
    save_production_batch(
        session, date(2026, 7, 14), Decimal("30"), product.product_id, Decimal("6")
    )
    with pytest.raises(ValueError, match="raw milk pool short"):
        delete_milk_collection(session, txn.txn_id)
