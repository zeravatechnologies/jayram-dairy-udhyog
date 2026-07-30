"""RawMaterialTransaction — one row per milk delivery.

Rows are created by milk collection and may be corrected in place via
the service layer (update/delete) when the owner fixes typos. Quantity
reductions are rejected if they would make the derived raw-milk pool
negative.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class RawMaterialTransaction(Base):
    __tablename__ = "raw_material_txn"

    txn_id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_id = Column(Integer, ForeignKey("vendor.vendor_id"), nullable=False)
    date = Column(Date, nullable=False)
    session = Column(String, nullable=False, default="morning")  # "morning" | "evening" | "advance"
    quantity_l = Column(Numeric(10, 3), nullable=False, default=0)
    fat_pct = Column(Numeric(5, 2))
    rate_applied = Column(Numeric(10, 4), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    vendor = relationship("Vendor", back_populates="transactions")

    def __repr__(self):
        return f"<RawMaterialTxn {self.txn_id} vendor={self.vendor_id} {self.quantity_l}L amt={self.amount}>"
