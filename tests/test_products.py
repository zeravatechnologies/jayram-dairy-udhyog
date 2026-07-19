"""Tests for product CRUD behavior."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.base import make_session_factory
from app.models.production_batch import ProductionBatch
from app.models.product import Product
from app.services.products import create_product, delete_product


@pytest.fixture
def session():
    session_factory = make_session_factory(":memory:")
    database_session = session_factory()
    yield database_session
    database_session.close()


def test_delete_product_removes_product_without_history(session):
    product = create_product(session, "Paneer")

    delete_product(session, product.product_id)

    assert session.get(Product, product.product_id) is None


def test_delete_product_rejects_product_with_production_history(session):
    product = create_product(session, "Paneer")
    session.add(
        ProductionBatch(
            date=date(2026, 7, 18),
            raw_milk_consumed_l=Decimal("5"),
            product_id=product.product_id,
            output_qty=Decimal("1"),
        )
    )
    session.commit()

    with pytest.raises(ValueError, match="existing production history"):
        delete_product(session, product.product_id)

    assert session.get(Product, product.product_id) is not None
