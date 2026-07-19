"""Product CRUD service."""
from decimal import Decimal
from sqlalchemy import select

from app.models.product import Product


def list_products(session):
    return session.execute(select(Product)).scalars().all()


def create_product(session, name, variant=None, unit="kg", conversion_ratio=None, initial_stock=0):
    if not name or not name.strip():
        raise ValueError("Product name is required")
    product = Product(
        name=name.strip(),
        variant=variant.strip() if variant else None,
        unit=unit,
        current_stock=Decimal(initial_stock),
        conversion_ratio=Decimal(conversion_ratio) if conversion_ratio else None,
    )
    session.add(product)
    session.commit()
    return product


def update_product(session, product_id, name=None, variant=None, unit=None, conversion_ratio=None):
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"No such product: {product_id}")
    if name is not None:
        if not name.strip():
            raise ValueError("Product name is required")
        product.name = name.strip()
    if variant is not None:
        product.variant = variant.strip() or None
    if unit is not None:
        product.unit = unit
    if conversion_ratio is not None:
        product.conversion_ratio = Decimal(conversion_ratio) if conversion_ratio else None
    session.commit()
    return product


def delete_product(session, product_id):
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"No such product: {product_id}")
    if product.batches:
        raise ValueError(
            "Can't delete a product with existing production history — "
            "this would break stock history. Consider archiving instead."
        )
    session.delete(product)
    session.commit()
