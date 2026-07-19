"""Running balance calculation.

Balances are NEVER stored — always computed as
(sum of transaction amounts) - (sum of payments), as of any date.
This is the transaction-first model from the proposal and architecture
doc Section 6. See architecture doc Section 7.2 for the pseudocode this
implements.
"""
from decimal import Decimal
from sqlalchemy import select, func

from app.models.transaction import RawMaterialTransaction
from app.models.order import OrderTransaction
from app.models.payment import Payment


def get_vendor_balance(session, vendor_id: int, as_of_date=None) -> Decimal:
    """Return what is currently owed TO this vendor (positive = we owe them)."""
    txn_q = select(func.coalesce(func.sum(RawMaterialTransaction.amount), 0)).where(
        RawMaterialTransaction.vendor_id == vendor_id
    )
    pay_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.party_type == "vendor", Payment.party_id == vendor_id
    )
    if as_of_date is not None:
        txn_q = txn_q.where(RawMaterialTransaction.date <= as_of_date)
        pay_q = pay_q.where(Payment.date <= as_of_date)

    total_owed = Decimal(session.execute(txn_q).scalar_one())
    total_paid = Decimal(session.execute(pay_q).scalar_one())
    return total_owed - total_paid


def get_customer_balance(session, customer_id: int, as_of_date=None) -> Decimal:
    """Return what this customer currently owes US (positive = they owe us)."""
    txn_q = select(func.coalesce(func.sum(OrderTransaction.amount), 0)).where(
        OrderTransaction.customer_id == customer_id
    )
    pay_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.party_type == "customer", Payment.party_id == customer_id
    )
    if as_of_date is not None:
        txn_q = txn_q.where(OrderTransaction.order_date <= as_of_date)
        pay_q = pay_q.where(Payment.date <= as_of_date)

    total_owed = Decimal(session.execute(txn_q).scalar_one())
    total_paid = Decimal(session.execute(pay_q).scalar_one())
    return total_owed - total_paid
