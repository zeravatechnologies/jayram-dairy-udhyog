"""Import all models here so Base.metadata knows about every table
before make_session_factory() calls create_all(). Without this, a
model that's never directly imported elsewhere would silently get no
table created.
"""
from app.models.vendor import Vendor
from app.models.transaction import RawMaterialTransaction
from app.models.payment import Payment
from app.models.product import Product
from app.models.production_batch import ProductionBatch
from app.models.customer import Customer
from app.models.order import OrderTransaction
from app.models.user import User

__all__ = [
    "Vendor", "RawMaterialTransaction", "Payment", "Product",
    "ProductionBatch", "Customer", "OrderTransaction", "User",
]
