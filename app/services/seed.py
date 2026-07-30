"""Demo seed data for local development runs only."""
from __future__ import annotations

import sys
from decimal import Decimal

from sqlalchemy import select

from app.models import Vendor, Product, Customer


def should_seed_demo_data() -> bool:
    """Packaged installs must start empty; source runs may seed."""
    return not getattr(sys, "frozen", False)


def seed_demo_data(Session) -> None:
    session = Session()
    existing = session.execute(select(Vendor)).scalars().first()
    if existing is None:
        session.add_all([
            Vendor(name="Hari Thapa", phone="9841000002", address="Mirchaiya",
                   pricing_mode="fat_based", default_rate=Decimal("9.42")),
            Vendor(name="Ram Bahadur", phone="9845000008", address="Siraha",
                   pricing_mode="flat_rate", default_rate=Decimal("58.00")),
        ])
    existing_product = session.execute(select(Product)).scalars().first()
    if existing_product is None:
        session.add_all([
            Product(name="Khuwa", unit="kg", current_stock=Decimal("20"), conversion_ratio=Decimal("5.0")),
            Product(name="Paneer", unit="kg", current_stock=Decimal("10"), conversion_ratio=Decimal("6.0")),
            Product(name="Dahi", variant="Cup Dahi", unit="pcs", current_stock=Decimal("30")),
        ])
    existing_customer = session.execute(select(Customer)).scalars().first()
    if existing_customer is None:
        session.add_all([
            Customer(name="Hotel Annapurna", phone="9801000001", address="Mirchaiya Bazaar",
                      type_tag="Hotel", credit_days=15),
            Customer(name="Shree Party Palace", phone="9823000007", address="Mirchaiya",
                      type_tag="Party Palace"),
        ])
    session.commit()
    session.close()
