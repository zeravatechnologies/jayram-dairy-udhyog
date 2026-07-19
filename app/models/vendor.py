"""Vendor (milkman) model.

pricing_mode is either "fat_based" or "flat_rate" — see
app/services/pricing.py for how each mode is applied.
"""
from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.orm import relationship

from app.models.base import Base


class Vendor(Base):
    __tablename__ = "vendor"

    vendor_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    address = Column(String)
    pricing_mode = Column(String, nullable=False, default="fat_based")  # "fat_based" | "flat_rate"
    default_rate = Column(Numeric(10, 2), nullable=False, default=0)   # flat rate/L, or fat-price-rate
    branch_id = Column(Integer, nullable=False, default=1)  # extension point — see architecture doc Section 5

    transactions = relationship("RawMaterialTransaction", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor {self.vendor_id} {self.name}>"
