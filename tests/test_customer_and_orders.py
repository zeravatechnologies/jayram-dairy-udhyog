"""Tests for Customer/Order — the mirror of the Vendor pattern, plus a
regression test for the linked_txn_id collision bug caught while
building this (vendor transactions and orders have independent ID
sequences, so payment lookups must filter by party_type too).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.models.order import OrderTransaction
from app.services.customers import create_customer, update_customer, delete_customer, list_customers
from app.services.products import create_product
from app.services.vendors import create_vendor
from app.services.milk_collection import record_milk_collection
from app.services.orders import (
    cancel_order,
    create_order,
    delete_order,
    deliver_order,
    list_upcoming_advance_orders,
    update_placed_order,
)
from app.services.balance import get_customer_balance
from app.services.payments import get_amount_paid_for_txn, get_txn_status
from app.utils.bs_date import today_in_nepal


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


@pytest.fixture
def product(session):
    p = create_product(session, "Khuwa", unit="kg")
    p.current_stock = Decimal("10.0")
    session.commit()
    return p


@pytest.fixture
def customer(session):
    return create_customer(session, "Hotel Annapurna", "9801000001", "Mirchaiya Bazaar", "Hotel", credit_days=15)


def test_create_and_list_customer(session):
    create_customer(session, "Shree Party Palace", "9823000007", "addr", "Party Palace")
    assert len(list_customers(session)) == 1


def test_create_customer_requires_name(session):
    with pytest.raises(ValueError, match="name is required"):
        create_customer(session, "  ", "123", "addr")


def test_delete_customer_blocked_if_has_orders(session, product, customer):
    create_order(session, customer.customer_id, product.product_id, date(2026, 7, 14), Decimal("2"), Decimal("380"))
    with pytest.raises(ValueError, match="existing order history"):
        delete_customer(session, customer.customer_id)


def test_create_order_decrements_stock(session, product, customer):
    assert product.current_stock == Decimal("10.0")
    order = create_order(session, customer.customer_id, product.product_id, date(2026, 7, 14), Decimal("3"), Decimal("380"))
    assert product.current_stock == Decimal("7.0")
    assert order.status == "delivered"


def test_create_order_persists_optional_delivery_date(session, product, customer):
    order = create_order(
        session,
        customer.customer_id,
        product.product_id,
        date(2026, 7, 14),
        Decimal("3"),
        Decimal("380"),
        delivery_date=date(2026, 7, 16),
        planning_note="Asked Hari for milk",
    )

    assert order.delivery_date == date(2026, 7, 16)
    assert order.status == "placed"
    assert order.planning_note == "Asked Hari for milk"
    assert product.current_stock == Decimal("10.0")  # advance — stock untouched


def test_create_order_rejects_delivery_before_order_date(session, product, customer):
    with pytest.raises(ValueError, match="cannot be before"):
        create_order(
            session,
            customer.customer_id,
            product.product_id,
            date(2026, 7, 14),
            Decimal("3"),
            Decimal("380"),
            delivery_date=date(2026, 7, 13),
        )


def test_create_order_rejects_insufficient_stock(session, product, customer):
    with pytest.raises(ValueError, match="Not enough stock"):
        create_order(session, customer.customer_id, product.product_id, date(2026, 7, 14), Decimal("999"), Decimal("380"))
    assert product.current_stock == Decimal("10.0")  # unchanged on rejection


def test_advance_order_allows_zero_stock(session, product, customer):
    product.current_stock = Decimal("0")
    session.commit()
    order = create_order(
        session,
        customer.customer_id,
        product.product_id,
        date(2026, 7, 14),
        Decimal("5"),
        Decimal("380"),
        delivery_date=date(2026, 8, 1),
    )
    assert order.status == "placed"
    assert product.current_stock == Decimal("0")


def test_deliver_advance_order_decrements_stock(session, product, customer):
    order = create_order(
        session,
        customer.customer_id,
        product.product_id,
        date(2026, 7, 14),
        Decimal("4"),
        Decimal("380"),
        delivery_date=date(2026, 8, 1),
    )
    assert product.current_stock == Decimal("10.0")
    deliver_order(session, order.order_id)
    assert product.current_stock == Decimal("6.0")
    assert order.status == "delivered"


def test_cancel_advance_order_excludes_from_balance(session, product, customer):
    order = create_order(
        session,
        customer.customer_id,
        product.product_id,
        date(2026, 7, 14),
        Decimal("5"),
        Decimal("380"),
        delivery_date=date(2026, 8, 1),
    )
    assert get_customer_balance(session, customer.customer_id) == Decimal("1900.00")
    cancel_order(session, order.order_id)
    assert order.status == "cancelled"
    assert get_customer_balance(session, customer.customer_id) == Decimal("0")
    assert product.current_stock == Decimal("10.0")


def test_list_upcoming_advance_orders(session, product, customer):
    create_order(
        session, customer.customer_id, product.product_id, today_in_nepal(),
        Decimal("2"), Decimal("380"),
        delivery_date=today_in_nepal() + timedelta(days=10),
    )
    upcoming = list_upcoming_advance_orders(session, within_days=30)
    assert len(upcoming) == 1


def test_create_order_exact_stock_amount_allowed(session, product, customer):
    # Same boundary case as production: selling exactly what's in stock must succeed.
    create_order(session, customer.customer_id, product.product_id, date(2026, 7, 14), Decimal("10.0"), Decimal("380"))
    assert product.current_stock == Decimal("0")


def test_customer_balance_after_order_with_advance(session, product, customer):
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("5"), Decimal("380"), advance_received_now=Decimal("500"),
    )
    assert order.amount == Decimal("1900.00")
    balance = get_customer_balance(session, customer.customer_id)
    assert balance == Decimal("1400.00")  # 1900 - 500 advance


def test_order_txn_id_does_not_collide_with_vendor_txn_id(session, product, customer):
    """Regression test: vendor transactions and orders have independent
    ID sequences. Before the fix, a vendor delivery #1 and an order #1
    could show each other's linked payments.
    """
    vendor = create_vendor(session, "Hari Thapa", "111", "addr", "flat_rate", Decimal("58"))
    vendor_txn = record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("4.0"), amount_paid_now=Decimal("50")
    )
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("2"), Decimal("380"), advance_received_now=Decimal("300"),
    )

    # Force the collision scenario: same numeric ID on both sides.
    assert vendor_txn.txn_id == order.order_id == 1

    vendor_paid = get_amount_paid_for_txn(session, vendor_txn.txn_id, party_type="vendor")
    order_paid = get_amount_paid_for_txn(session, order.order_id, party_type="customer")

    assert vendor_paid == Decimal("50")     # only the vendor's own payment
    assert order_paid == Decimal("300")     # only the order's own payment, NOT 350


def test_update_placed_order_recalculates_amount(session, product, customer):
    order = create_order(
        session,
        customer.customer_id,
        product.product_id,
        date(2026, 7, 14),
        Decimal("5"),
        Decimal("380"),
        delivery_date=date(2026, 7, 20),
        advance_received_now=Decimal("100"),
    )
    assert product.current_stock == Decimal("10.0")

    updated = update_placed_order(
        session,
        order.order_id,
        quantity=Decimal("3"),
        rate=Decimal("400"),
        delivery_date=date(2026, 7, 22),
        planning_note="Corrected qty",
        advance_received_now=Decimal("200"),
    )
    assert updated.quantity == Decimal("3")
    assert updated.rate == Decimal("400")
    assert updated.amount == Decimal("1200.00")
    assert updated.delivery_date == date(2026, 7, 22)
    assert updated.planning_note == "Corrected qty"
    assert get_amount_paid_for_txn(session, order.order_id, "customer") == Decimal("200")
    assert product.current_stock == Decimal("10.0")  # still untouched
    assert get_customer_balance(session, customer.customer_id) == Decimal("1000.00")


def test_update_placed_order_rejects_delivered(session, product, customer):
    order = create_order(
        session,
        customer.customer_id,
        product.product_id,
        date(2026, 7, 14),
        Decimal("2"),
        Decimal("380"),
    )
    assert order.status == "delivered"
    with pytest.raises(ValueError, match="Only placed"):
        update_placed_order(
            session,
            order.order_id,
            quantity=Decimal("1"),
            rate=Decimal("380"),
            delivery_date=date(2026, 7, 20),
        )


def test_delete_delivered_order_restores_stock(session, product, customer):
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("3"), Decimal("380"),
    )
    assert product.current_stock == Decimal("7.0")
    assert get_customer_balance(session, customer.customer_id) == Decimal("1140.00")

    delete_order(session, order.order_id)

    assert session.get(OrderTransaction, order.order_id) is None
    assert product.current_stock == Decimal("10.0")
    assert get_customer_balance(session, customer.customer_id) == Decimal("0")


def test_delete_delivered_order_removes_linked_payment(session, product, customer):
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("5"), Decimal("380"), advance_received_now=Decimal("500"),
    )
    order_id = order.order_id
    assert get_amount_paid_for_txn(session, order_id, "customer") == Decimal("500")

    delete_order(session, order_id)

    assert get_amount_paid_for_txn(session, order_id, "customer") == Decimal("0")
    assert get_customer_balance(session, customer.customer_id) == Decimal("0")
    assert product.current_stock == Decimal("10.0")


def test_delete_placed_advance_leaves_stock_unchanged(session, product, customer):
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("5"), Decimal("380"),
        delivery_date=date(2026, 8, 1),
    )
    assert product.current_stock == Decimal("10.0")
    assert get_customer_balance(session, customer.customer_id) == Decimal("1900.00")

    delete_order(session, order.order_id)

    assert session.get(OrderTransaction, order.order_id) is None
    assert product.current_stock == Decimal("10.0")
    assert get_customer_balance(session, customer.customer_id) == Decimal("0")


def test_delete_cancelled_order(session, product, customer):
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("5"), Decimal("380"),
        delivery_date=date(2026, 8, 1),
    )
    cancel_order(session, order.order_id)
    order_id = order.order_id

    delete_order(session, order_id)

    assert session.get(OrderTransaction, order_id) is None
    assert product.current_stock == Decimal("10.0")


def test_delete_order_unknown_id(session):
    with pytest.raises(ValueError, match="No such order"):
        delete_order(session, 99999)
