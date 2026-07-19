"""Tests for app.services.production — the second and last piece of
genuinely risky logic in the app: pooled raw-milk inventory.

Deliberately tests the POOLED behavior explicitly — milk from multiple
different vendors must combine into one shared total, and production
must draw from that shared total, not any single vendor's delivery.
This is the confirmed decision from discovery, so it's worth pinning
down hard here.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.services.vendors import create_vendor
from app.services.milk_collection import record_milk_collection
from app.services.products import create_product
from app.services.production import get_pool_available, save_production_batch


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


@pytest.fixture
def product(session):
    return create_product(session, "Khuwa", unit="kg", conversion_ratio=Decimal("5.0"))


def test_pool_zero_with_no_deliveries(session):
    assert get_pool_available(session) == Decimal("0")


def test_pool_combines_multiple_vendors(session):
    # This is the core "pooled, not per-vendor" behavior confirmed with the owner.
    v1 = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    v2 = create_vendor(session, "Ram Bahadur", "222", "addr", "flat_rate", Decimal("55"))
    record_milk_collection(session, v1.vendor_id, date(2026, 7, 14), Decimal("10.0"))
    record_milk_collection(session, v2.vendor_id, date(2026, 7, 14), Decimal("15.0"))

    pool = get_pool_available(session)
    assert pool == Decimal("25.0")  # combined across BOTH vendors, not per-vendor


def test_save_batch_deducts_from_pool(session, product):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("40.0"))

    save_production_batch(session, date(2026, 7, 14), Decimal("15.0"), product.product_id, Decimal("3.0"))

    pool = get_pool_available(session)
    assert pool == Decimal("25.0")  # 40 collected - 15 consumed


def test_save_batch_increments_product_stock(session, product):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("40.0"))

    assert product.current_stock == Decimal("0")
    save_production_batch(session, date(2026, 7, 14), Decimal("15.0"), product.product_id, Decimal("3.0"))
    assert product.current_stock == Decimal("3.0")

    save_production_batch(session, date(2026, 7, 14), Decimal("10.0"), product.product_id, Decimal("2.0"))
    assert product.current_stock == Decimal("5.0")  # cumulative across batches


def test_save_batch_persists_optional_expiry_date(session, product):
    vendor = create_vendor(
        session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58")
    )
    record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("40.0")
    )

    batch = save_production_batch(
        session,
        date(2026, 7, 14),
        Decimal("15.0"),
        product.product_id,
        Decimal("3.0"),
        expiry_date=date(2026, 7, 21),
    )

    assert batch.expiry_date == date(2026, 7, 21)


def test_save_batch_rejects_expiry_before_production_date(session, product):
    with pytest.raises(ValueError, match="cannot be before"):
        save_production_batch(
            session,
            date(2026, 7, 14),
            Decimal("1.0"),
            product.product_id,
            Decimal("1.0"),
            expiry_date=date(2026, 7, 13),
        )


def test_save_batch_rejects_when_pool_insufficient(session, product):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("10.0"))

    with pytest.raises(ValueError, match="Not enough raw milk in pool") as error:
        save_production_batch(session, date(2026, 7, 14), Decimal("15.0"), product.product_id, Decimal("3.0"))

    assert "(BS)" in str(error.value)
    assert "2026-07-14" not in str(error.value)
    # and stock must NOT have changed on a rejected batch
    assert product.current_stock == Decimal("0")


def test_save_batch_rejects_zero_or_negative_inputs(session, product):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("40.0"))

    with pytest.raises(ValueError, match="greater than zero"):
        save_production_batch(session, date(2026, 7, 14), Decimal("0"), product.product_id, Decimal("3.0"))
    with pytest.raises(ValueError, match="greater than zero"):
        save_production_batch(session, date(2026, 7, 14), Decimal("10.0"), product.product_id, Decimal("0"))


def test_save_batch_rejects_unknown_product(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("40.0"))

    with pytest.raises(ValueError, match="No such product"):
        save_production_batch(session, date(2026, 7, 14), Decimal("10.0"), 999, Decimal("2.0"))


def test_pool_as_of_date_excludes_later_deliveries(session):
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 13), Decimal("10.0"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("20.0"))

    pool_on_13th = get_pool_available(session, as_of_date=date(2026, 7, 13))
    pool_on_14th = get_pool_available(session, as_of_date=date(2026, 7, 14))
    assert pool_on_13th == Decimal("10.0")
    assert pool_on_14th == Decimal("30.0")


def test_exact_pool_amount_is_allowed_not_just_less_than(session, product):
    # Boundary case: consuming EXACTLY what's available should succeed, not be
    # rejected by an off-by-one comparison (> vs >=).
    v = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    record_milk_collection(session, v.vendor_id, date(2026, 7, 14), Decimal("10.0"))

    save_production_batch(session, date(2026, 7, 14), Decimal("10.0"), product.product_id, Decimal("2.0"))
    assert get_pool_available(session) == Decimal("0")
