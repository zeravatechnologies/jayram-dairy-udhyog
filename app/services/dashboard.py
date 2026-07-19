"""Dashboard aggregate stats — today's milk collected, total vendor
payable, total customer due, low stock products. Each figure is
computed fresh from the same tested balance/pool functions already
used elsewhere — no separate "dashboard-only" logic that could drift
out of sync with the real ledgers.
"""
from datetime import date as date_type
from decimal import Decimal
from sqlalchemy import select, func

from app.models.transaction import RawMaterialTransaction
from app.models.vendor import Vendor
from app.models.customer import Customer
from app.models.product import Product
from app.services.balance import get_vendor_balance, get_customer_balance
from app.utils.bs_date import today_in_nepal

DEFAULT_LOW_STOCK_THRESHOLD = Decimal("5")


def get_today_milk_total(session, today: date_type | None = None) -> Decimal:
    today = today or today_in_nepal()
    q = select(func.coalesce(func.sum(RawMaterialTransaction.quantity_l), 0)).where(
        RawMaterialTransaction.date == today
    )
    return Decimal(session.execute(q).scalar_one())


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
