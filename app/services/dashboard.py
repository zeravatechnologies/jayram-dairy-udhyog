"""Dashboard aggregate stats — today's milk collected, total vendor
payable, total customer due, low stock products. Each figure is
computed fresh from the same tested balance/pool functions already
used elsewhere — no separate "dashboard-only" logic that could drift
out of sync with the real ledgers.
"""
from datetime import date as date_type, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.models.customer import Customer
from app.models.product import Product
from app.models.transaction import RawMaterialTransaction
from app.models.vendor import Vendor
from app.services.balance import get_customer_balance, get_vendor_balance
from app.utils.bs_date import today_in_nepal

DEFAULT_LOW_STOCK_THRESHOLD = Decimal("5")


def _as_date(value: date_type | datetime | None) -> date_type:
    """Normalize to a civil date so SQLite/Date comparisons stay exact."""
    if value is None:
        return today_in_nepal()
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, date_type):
        raise ValueError("Expected a date")
    return value


def get_today_milk_total(session, today: date_type | None = None) -> Decimal:
    """Sum all milk collected on the given Nepal business day (every session)."""
    today = _as_date(today)
    q = select(func.coalesce(func.sum(RawMaterialTransaction.quantity_l), 0)).where(
        RawMaterialTransaction.date == today
    )
    return Decimal(session.execute(q).scalar_one())


def get_today_milk_by_session(session, today: date_type | None = None) -> dict[str, Decimal]:
    """Per-session litres for today. Keys always include morning and evening."""
    today = _as_date(today)
    rows = session.execute(
        select(
            RawMaterialTransaction.session,
            func.coalesce(func.sum(RawMaterialTransaction.quantity_l), 0),
        )
        .where(RawMaterialTransaction.date == today)
        .group_by(RawMaterialTransaction.session)
    ).all()

    totals = {label: Decimal("0") for label in ("morning", "evening")}
    for session_label, qty in rows:
        key = (session_label or "morning").lower()
        if key not in totals:
            totals[key] = Decimal("0")
        totals[key] += Decimal(qty)
    return totals


def get_total_vendor_payable(session) -> Decimal:
    """Sum of positive balances owed TO vendors (a vendor who's overpaid,
    i.e. a negative balance, doesn't offset what's owed to others)."""
    vendors = session.execute(select(Vendor)).scalars().all()
    total = Decimal("0")
    for v in vendors:
        balance = get_vendor_balance(session, v.vendor_id)
        if balance > 0:
            total += balance
    return total


def get_total_customer_due(session) -> Decimal:
    customers = session.execute(select(Customer)).scalars().all()
    total = Decimal("0")
    for c in customers:
        balance = get_customer_balance(session, c.customer_id)
        if balance > 0:
            total += balance
    return total


def get_low_stock_products(session, threshold: Decimal = DEFAULT_LOW_STOCK_THRESHOLD):
    products = session.execute(select(Product)).scalars().all()
    return [p for p in products if Decimal(p.current_stock) < threshold]
