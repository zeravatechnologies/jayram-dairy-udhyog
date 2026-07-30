"""Tests for PDF export helpers."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.base import make_session_factory
from app.services.customers import create_customer
from app.services.milk_collection import record_milk_collection
from app.services.orders import create_order
from app.services.payments import record_payment
from app.services.pdf_export import (
    write_customer_statement,
    write_order_payment_history,
    write_payment_receipt,
    write_vendor_statement,
)
from app.services.products import create_product
from app.services.vendors import create_vendor


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


def test_write_payment_receipt(session, tmp_path: Path):
    vendor = create_vendor(session, "Hari Thapa", "1", "a", "flat_rate", Decimal("58"))
    payment = record_payment(
        session, "vendor", vendor.vendor_id, Decimal("100"), date(2026, 7, 14),
    )
    out = tmp_path / "receipt.pdf"
    write_payment_receipt(session, payment.payment_id, str(out))
    assert out.is_file()
    assert out.stat().st_size > 0


def test_write_vendor_statement(session, tmp_path: Path):
    vendor = create_vendor(session, "Hari Thapa", "1", "a", "flat_rate", Decimal("58"))
    record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("10"),
        session_label="morning", amount_paid_now=Decimal("100"),
    )
    record_milk_collection(
        session, vendor.vendor_id, date(2026, 7, 14), Decimal("5"),
        session_label="evening",
    )
    out = tmp_path / "vendor.pdf"
    write_vendor_statement(session, vendor.vendor_id, str(out))
    assert out.is_file()
    assert out.stat().st_size > 0


def test_write_customer_and_order_pdfs(session, tmp_path: Path):
    product = create_product(session, "Khuwa", unit="kg")
    product.current_stock = Decimal("20")
    session.commit()
    customer = create_customer(session, "Hotel Annapurna", "1", "a")
    order = create_order(
        session, customer.customer_id, product.product_id, date(2026, 7, 14),
        Decimal("2"), Decimal("380"), advance_received_now=Decimal("100"),
    )
    customer_pdf = tmp_path / "customer.pdf"
    order_pdf = tmp_path / "order.pdf"
    write_customer_statement(session, customer.customer_id, str(customer_pdf))
    write_order_payment_history(session, order.order_id, str(order_pdf))
    assert customer_pdf.is_file() and customer_pdf.stat().st_size > 0
    assert order_pdf.is_file() and order_pdf.stat().st_size > 0
