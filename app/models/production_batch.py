"""ProductionBatch — one manufacturing run, consuming pooled raw milk
and producing finished-goods stock.

Append-only, same discipline as RawMaterialTransaction — a correction
is a new (possibly negative-adjusting) row, never an edit to history.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class ProductionBatch(Base):
    __tablename__ = "production_batch"

    batch_id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    raw_milk_consumed_l = Column(Numeric(10, 3), nullable=False)
    product_id = Column(Integer, ForeignKey("product.product_id"), nullable=False)
    output_qty = Column(Numeric(10, 3), nullable=False)
    expiry_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product", back_populates="batches")

    def __repr__(self):
        return f"<ProductionBatch {self.batch_id} product={self.product_id} consumed={self.raw_milk_consumed_l}L>"
