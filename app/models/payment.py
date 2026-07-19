"""Payment — any money movement, optionally linked to a specific transaction.

party_type is "vendor" or "customer"; party_id points at Vendor.vendor_id
or Customer.customer_id respectively. This is enforced in the service
layer, not the database — SQLite has no native polymorphic FK support.
See architecture doc Section 6 for why this is an intentional tradeoff.

linked_txn_id, if set, points at a RawMaterialTransaction.txn_id (for
vendor payments) or an OrderTransaction.order_id (for customer payments) —
again resolved by party_type in the service layer, not a real FK.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func

from app.models.base import Base


class Payment(Base):
    __tablename__ = "payment"

    payment_id = Column(Integer, primary_key=True, autoincrement=True)
    party_type = Column(String, nullable=False)   # "vendor" | "customer"
    party_id = Column(Integer, nullable=False)
    linked_txn_id = Column(Integer, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="paid")  # "paid" | "pending" | "processing"
    mode = Column(String, nullable=False, default="advance")  # "advance" | "installment" | "full" | "partial"
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Payment {self.payment_id} {self.party_type}#{self.party_id} amt={self.amount}>"
