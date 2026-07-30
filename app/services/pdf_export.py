"""PDF export for payment receipts and party/order statements.

Uses reportlab with the bundled Noto Sans Devanagari font so BS dates
and Nepali labels render correctly on Windows installs without relying
on system fonts.
"""
from __future__ import annotations

import sys
from datetime import date as date_type
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.customer import Customer
from app.models.order import OrderTransaction
from app.models.transaction import RawMaterialTransaction
from app.models.vendor import Vendor
from app.services.balance import get_customer_balance, get_vendor_balance
from app.services.payments import (
    get_payment,
    list_payments_for_party,
    list_payments_for_txn,
)
from app.utils.bs_date import to_bs_display, today_in_nepal
from sqlalchemy import select

SHOP_NAME = "Jayram Dairy Udhyog"
_FONT_REGISTERED = False
_FONT_NAME = "Helvetica"


def _font_path() -> Path | None:
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(
            Path(sys._MEIPASS) / "app" / "assets" / "fonts" / "NotoSansDevanagari-Regular.ttf"
        )
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "assets" / "fonts" / "NotoSansDevanagari-Regular.ttf")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _ensure_font() -> str:
    global _FONT_REGISTERED, _FONT_NAME
    if _FONT_REGISTERED:
        return _FONT_NAME
    path = _font_path()
    if path is not None:
        pdfmetrics.registerFont(TTFont("NotoSansDevanagari", str(path)))
        _FONT_NAME = "NotoSansDevanagari"
    _FONT_REGISTERED = True
    return _FONT_NAME


def _styles():
    font = _ensure_font()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PdfTitle", parent=base["Heading1"], fontName=font, fontSize=16, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "PdfSubtitle", parent=base["Normal"], fontName=font, fontSize=10, textColor=colors.grey,
        ),
        "body": ParagraphStyle(
            "PdfBody", parent=base["Normal"], fontName=font, fontSize=10, leading=14,
        ),
        "heading": ParagraphStyle(
            "PdfHeading", parent=base["Heading2"], fontName=font, fontSize=12, spaceBefore=10, spaceAfter=4,
        ),
    }


def _money(value: Decimal | int | str) -> str:
    return f"Rs {Decimal(value)}"


def _table(data: list[list], col_widths=None) -> Table:
    font = _ensure_font()
    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), font),
                ("FONTNAME", (0, 1), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.15, 0.35, 0.25)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.7, 0.7, 0.7)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _build_doc(path: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )


def write_payment_receipt(session, payment_id: int, output_path: str) -> str:
    payment = get_payment(session, payment_id)
    if payment is None:
        raise ValueError(f"No such payment: {payment_id}")

    if payment.party_type == "vendor":
        party = session.get(Vendor, payment.party_id)
    else:
        party = session.get(Customer, payment.party_id)
    party_name = party.name if party else f"(deleted {payment.party_type} #{payment.party_id})"

    styles = _styles()
    story = [
        Paragraph(SHOP_NAME, styles["title"]),
        Paragraph("Payment receipt", styles["subtitle"]),
        Spacer(1, 8),
        Paragraph(f"Receipt no: {payment.payment_id}", styles["body"]),
        Paragraph(f"Date (BS): {to_bs_display(payment.date)}", styles["body"]),
        Paragraph(f"Party: {party_name} ({payment.party_type})", styles["body"]),
        Paragraph(f"Mode: {payment.mode}", styles["body"]),
        Paragraph(f"Status: {payment.status}", styles["body"]),
        Paragraph(f"Amount: {_money(payment.amount)}", styles["body"]),
    ]
    if payment.linked_txn_id is not None:
        story.append(
            Paragraph(
                f"Linked to {payment.party_type} txn/order #{payment.linked_txn_id}",
                styles["body"],
            )
        )
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            f"Generated on {to_bs_display(today_in_nepal())}",
            styles["subtitle"],
        )
    )
    _build_doc(output_path).build(story)
    return output_path


def write_vendor_statement(
    session,
    vendor_id: int,
    output_path: str,
    from_date: date_type | None = None,
    to_date: date_type | None = None,
) -> str:
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise ValueError(f"No such vendor: {vendor_id}")

    milk_q = select(RawMaterialTransaction).where(
        RawMaterialTransaction.vendor_id == vendor_id
    )
    if from_date is not None:
        milk_q = milk_q.where(RawMaterialTransaction.date >= from_date)
    if to_date is not None:
        milk_q = milk_q.where(RawMaterialTransaction.date <= to_date)
    milk_rows = session.execute(
        milk_q.order_by(RawMaterialTransaction.date.asc(), RawMaterialTransaction.txn_id.asc())
    ).scalars().all()

    payments = list_payments_for_party(session, "vendor", vendor_id)
    if from_date is not None:
        payments = [p for p in payments if p.date >= from_date]
    if to_date is not None:
        payments = [p for p in payments if p.date <= to_date]

    balance = get_vendor_balance(session, vendor_id)
    styles = _styles()
    story = [
        Paragraph(SHOP_NAME, styles["title"]),
        Paragraph(f"Vendor statement — {vendor.name}", styles["subtitle"]),
        Spacer(1, 6),
        Paragraph(f"Phone: {vendor.phone or '—'}", styles["body"]),
        Paragraph(f"Address: {vendor.address or '—'}", styles["body"]),
        Paragraph(f"Closing balance owed to vendor: {_money(balance)}", styles["body"]),
        Paragraph(f"Generated on {to_bs_display(today_in_nepal())}", styles["subtitle"]),
        Paragraph("Milk collections", styles["heading"]),
    ]

    milk_data = [["Date (BS)", "Session", "Qty (L)", "Fat %", "Rate", "Amount"]]
    for txn in milk_rows:
        milk_data.append([
            to_bs_display(txn.date),
            txn.session or "—",
            str(txn.quantity_l),
            str(txn.fat_pct) if txn.fat_pct is not None else "—",
            str(txn.rate_applied),
            str(txn.amount),
        ])
    if len(milk_data) == 1:
        milk_data.append(["—", "—", "—", "—", "—", "—"])
    story.append(_table(milk_data, col_widths=[90, 55, 50, 45, 55, 60]))
    story.append(Paragraph("Payments", styles["heading"]))

    pay_data = [["Date (BS)", "Mode", "Linked", "Amount", "Status"]]
    for payment in payments:
        pay_data.append([
            to_bs_display(payment.date),
            payment.mode,
            str(payment.linked_txn_id) if payment.linked_txn_id else "—",
            str(payment.amount),
            payment.status,
        ])
    if len(pay_data) == 1:
        pay_data.append(["—", "—", "—", "—", "—"])
    story.append(_table(pay_data, col_widths=[90, 70, 50, 60, 55]))
    _build_doc(output_path).build(story)
    return output_path


def write_customer_statement(
    session,
    customer_id: int,
    output_path: str,
    from_date: date_type | None = None,
    to_date: date_type | None = None,
) -> str:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"No such customer: {customer_id}")

    order_q = select(OrderTransaction).where(OrderTransaction.customer_id == customer_id)
    if from_date is not None:
        order_q = order_q.where(OrderTransaction.order_date >= from_date)
    if to_date is not None:
        order_q = order_q.where(OrderTransaction.order_date <= to_date)
    orders = session.execute(
        order_q.order_by(OrderTransaction.order_date.asc(), OrderTransaction.order_id.asc())
    ).scalars().all()

    payments = list_payments_for_party(session, "customer", customer_id)
    if from_date is not None:
        payments = [p for p in payments if p.date >= from_date]
    if to_date is not None:
        payments = [p for p in payments if p.date <= to_date]

    balance = get_customer_balance(session, customer_id)
    styles = _styles()
    story = [
        Paragraph(SHOP_NAME, styles["title"]),
        Paragraph(f"Customer statement — {customer.name}", styles["subtitle"]),
        Spacer(1, 6),
        Paragraph(f"Phone: {customer.phone or '—'}", styles["body"]),
        Paragraph(f"Address: {customer.address or '—'}", styles["body"]),
        Paragraph(f"Closing balance due from customer: {_money(balance)}", styles["body"]),
        Paragraph(f"Generated on {to_bs_display(today_in_nepal())}", styles["subtitle"]),
        Paragraph("Orders", styles["heading"]),
    ]

    order_data = [["Order (BS)", "Delivery", "Product", "Qty", "Amount", "Status"]]
    for order in orders:
        product_label = (
            f"{order.product.name} ({order.product.variant})"
            if order.product.variant
            else order.product.name
        )
        order_data.append([
            to_bs_display(order.order_date),
            to_bs_display(order.delivery_date) if order.delivery_date else "—",
            product_label,
            str(order.quantity),
            str(order.amount),
            order.status,
        ])
    if len(order_data) == 1:
        order_data.append(["—", "—", "—", "—", "—", "—"])
    story.append(_table(order_data, col_widths=[75, 75, 90, 40, 55, 50]))
    story.append(Paragraph("Payments", styles["heading"]))

    pay_data = [["Date (BS)", "Mode", "Linked order", "Amount", "Status"]]
    for payment in payments:
        pay_data.append([
            to_bs_display(payment.date),
            payment.mode,
            str(payment.linked_txn_id) if payment.linked_txn_id else "—",
            str(payment.amount),
            payment.status,
        ])
    if len(pay_data) == 1:
        pay_data.append(["—", "—", "—", "—", "—"])
    story.append(_table(pay_data, col_widths=[90, 70, 60, 60, 55]))
    _build_doc(output_path).build(story)
    return output_path


def write_order_payment_history(session, order_id: int, output_path: str) -> str:
    order = session.get(OrderTransaction, order_id)
    if order is None:
        raise ValueError(f"No such order: {order_id}")

    payments = list_payments_for_txn(session, order_id, party_type="customer")
    paid = sum((Decimal(p.amount) for p in payments), Decimal("0"))
    due = Decimal(order.amount) - paid
    product_label = (
        f"{order.product.name} ({order.product.variant})"
        if order.product.variant
        else order.product.name
    )

    styles = _styles()
    story = [
        Paragraph(SHOP_NAME, styles["title"]),
        Paragraph(f"Order payment history — #{order.order_id}", styles["subtitle"]),
        Spacer(1, 6),
        Paragraph(f"Customer: {order.customer.name}", styles["body"]),
        Paragraph(f"Product: {product_label}", styles["body"]),
        Paragraph(f"Order date (BS): {to_bs_display(order.order_date)}", styles["body"]),
        Paragraph(
            f"Delivery (BS): {to_bs_display(order.delivery_date) if order.delivery_date else '—'}",
            styles["body"],
        ),
        Paragraph(f"Quantity: {order.quantity} @ {order.rate}", styles["body"]),
        Paragraph(f"Order amount: {_money(order.amount)}", styles["body"]),
        Paragraph(f"Order status: {order.status}", styles["body"]),
        Paragraph(f"Paid: {_money(paid)} · Due: {_money(due)}", styles["body"]),
        Paragraph("Payments against this order", styles["heading"]),
    ]

    pay_data = [["Date (BS)", "Mode", "Amount", "Status"]]
    for payment in payments:
        pay_data.append([
            to_bs_display(payment.date),
            payment.mode,
            str(payment.amount),
            payment.status,
        ])
    if len(pay_data) == 1:
        pay_data.append(["—", "—", "—", "—"])
    story.append(_table(pay_data, col_widths=[100, 80, 70, 60]))
    if order.planning_note:
        story.append(Paragraph(f"Planning note: {order.planning_note}", styles["body"]))
    story.append(
        Paragraph(f"Generated on {to_bs_display(today_in_nepal())}", styles["subtitle"])
    )
    _build_doc(output_path).build(story)
    return output_path
