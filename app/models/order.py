"""OrderTransaction — one row per order/sale. Append-only, same
discipline as RawMaterialTransaction. Sells FROM product stock, so
saving an order also decrements the product's current_stock.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class OrderTransaction(Base):
    __tablename__ = "order_txn"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customer.customer_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.product_id"), nullable=False)
    order_date = Column(Date, nullable=False)
    delivery_date = Column(Date, nullable=True)
    quantity = Column(Numeric(10, 3), nullable=False)
    rate = Column(Numeric(10, 2), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="placed")  # "placed" | "delivered" | "cancelled"
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product")

    def __repr__(self):
        return f"<OrderTxn {self.order_id} customer={self.customer_id} amt={self.amount}>"
