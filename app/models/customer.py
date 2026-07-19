"""Customer — buyer of finished goods (hotels, party palaces, retail,
or any future type). type_tag is free text, owner-editable, per the
confirmed decision: no fixed categories.
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class Customer(Base):
    __tablename__ = "customer"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    address = Column(String)
    type_tag = Column(String, nullable=True)  # free text: "Hotel", "Party Palace", etc.
    credit_days = Column(Integer, nullable=True)  # e.g. 15 = pay within 15 days; null = pay on delivery
    branch_id = Column(Integer, nullable=False, default=1)  # extension point, matches Vendor

    orders = relationship("OrderTransaction", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.customer_id} {self.name}>"
