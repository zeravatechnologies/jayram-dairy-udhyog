"""Product — finished goods held as sellable stock (khuwa, paneer, dahi...).

variant handles cases like Dahi (Normal/Cup) or Mithai (White/Black/Cream)
per the product list confirmed earlier — kept as a plain field rather
than a separate table since variants don't need their own attributes
beyond a name.
"""
from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.orm import relationship

from app.models.base import Base


class Product(Base):
    __tablename__ = "product"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    variant = Column(String, nullable=True)  # e.g. "Cup Dahi", "Mithai (White)" — nullable for products with no variant
    unit = Column(String, nullable=False, default="kg")
    current_stock = Column(Numeric(10, 3), nullable=False, default=0)
    conversion_ratio = Column(Numeric(10, 4), nullable=True)  # informational: e.g. litres of milk per unit of product

    batches = relationship("ProductionBatch", back_populates="product")

    def __repr__(self):
        label = f"{self.name} ({self.variant})" if self.variant else self.name
        return f"<Product {self.product_id} {label}>"
