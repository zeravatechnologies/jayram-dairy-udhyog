"""Production service — pooled raw-milk inventory and production batches.

This is the second (and last) piece of genuinely risky logic in the
app, per architecture doc Section 7.3. Confirmed with the owner: raw
milk consumed in a batch is drawn from a single POOLED total across
ALL vendors — not traced back to a specific vendor's delivery.
"""
from datetime import date as date_type, datetime
from decimal import Decimal
from sqlalchemy import select, func

from app.models.transaction import RawMaterialTransaction
from app.models.production_batch import ProductionBatch
from app.models.product import Product
from app.utils.bs_date import to_bs_display


def get_pool_available(session, as_of_date=None) -> Decimal:
    """Raw milk currently available to consume in production.

    = (total milk collected from all vendors) - (total already consumed
    in production batches), as of any date. Never stored — always
    computed, same transaction-first discipline as vendor/customer
    balances.
    """
    collected_q = select(func.coalesce(func.sum(RawMaterialTransaction.quantity_l), 0))
    consumed_q = select(func.coalesce(func.sum(ProductionBatch.raw_milk_consumed_l), 0))

    if as_of_date is not None:
        collected_q = collected_q.where(RawMaterialTransaction.date <= as_of_date)
        consumed_q = consumed_q.where(ProductionBatch.date <= as_of_date)

    total_collected = Decimal(session.execute(collected_q).scalar_one())
    total_consumed = Decimal(session.execute(consumed_q).scalar_one())
    return total_collected - total_consumed


def save_production_batch(
    session,
    production_date: date_type,
    raw_milk_consumed_l: Decimal,
    product_id: int,
    output_qty: Decimal,
    expiry_date: date_type | None = None,
) -> ProductionBatch:
    """Record one production batch. Deducts from the pool, adds to stock.

    Raises ValueError if there isn't enough raw milk in the pool, or if
    inputs are invalid — the UI turns this into a friendly message per
    the deployment doc's error-handling philosophy, never a raw traceback.
    """
    if not isinstance(production_date, date_type) or isinstance(production_date, datetime):
        raise ValueError("Production date must be a valid date")
    if expiry_date is not None:
        if not isinstance(expiry_date, date_type) or isinstance(expiry_date, datetime):
            raise ValueError("Expiry date must be a valid date")
        if expiry_date < production_date:
            raise ValueError("Expiry date cannot be before the production date")

    raw_milk_consumed_l = Decimal(raw_milk_consumed_l)
    output_qty = Decimal(output_qty)

    if raw_milk_consumed_l <= 0:
        raise ValueError("Raw milk consumed must be greater than zero")
    if output_qty <= 0:
        raise ValueError("Output quantity must be greater than zero")

    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"No such product: {product_id}")

    pool_available = get_pool_available(session, as_of_date=production_date)
    if raw_milk_consumed_l > pool_available:
        raise ValueError(
            f"Not enough raw milk in pool: need {raw_milk_consumed_l}L, "
            f"only {pool_available}L available as of {to_bs_display(production_date)} (BS)"
        )

    batch = ProductionBatch(
        date=production_date,
        raw_milk_consumed_l=raw_milk_consumed_l,
        product_id=product_id,
        output_qty=output_qty,
        expiry_date=expiry_date,
    )
    session.add(batch)

    product.current_stock = Decimal(product.current_stock) + output_qty

    session.commit()
    return batch
