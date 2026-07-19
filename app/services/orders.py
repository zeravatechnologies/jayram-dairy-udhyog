"""Order service — the customer-side mirror of milk_collection.py.

Selling a product decrements its stock (the inverse of a production
batch incrementing it), and — same pattern as vendor payments — an
order can optionally have an advance/payment linked to it at the
moment it's created.
"""
from datetime import date as date_type, datetime
from decimal import Decimal

from app.models.customer import Customer
from app.models.product import Product
from app.models.order import OrderTransaction
from app.models.payment import Payment


def create_order(
    session,
    customer_id: int,
    product_id: int,
    order_date: date_type,
    quantity: Decimal,
    rate: Decimal,
    delivery_date: date_type | None = None,
    advance_received_now: Decimal | None = None,
) -> OrderTransaction:
    """Create an order, decrement product stock, and optionally record
    an advance payment linked to it. Raises ValueError on bad input —
    unknown customer/product, non-positive quantity/rate, or insufficient
    stock — same error-handling philosophy as the rest of the app.
    """
    if not isinstance(order_date, date_type) or isinstance(order_date, datetime):
        raise ValueError("Order date must be a valid date")
    if delivery_date is not None:
        if not isinstance(delivery_date, date_type) or isinstance(delivery_date, datetime):
            raise ValueError("Delivery date must be a valid date")
        if delivery_date < order_date:
            raise ValueError("Delivery date cannot be before the order date")

    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"No such customer: {customer_id}")
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"No such product: {product_id}")

    quantity = Decimal(quantity)
    rate = Decimal(rate)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if rate < 0:
        raise ValueError("Rate cannot be negative")
    if quantity > Decimal(product.current_stock):
        raise ValueError(
            f"Not enough stock: ordering {quantity} {product.unit}, "
            f"only {product.current_stock} {product.unit} in stock"
        )

    amount = (quantity * rate).quantize(Decimal("0.01"))

    order = OrderTransaction(
        customer_id=customer_id,
        product_id=product_id,
        order_date=order_date,
        delivery_date=delivery_date,
        quantity=quantity,
        rate=rate,
        amount=amount,
        status="placed",
    )
    session.add(order)
    session.flush()  # get order.order_id before linking a payment

    product.current_stock = Decimal(product.current_stock) - quantity

    if advance_received_now is not None and Decimal(advance_received_now) > 0:
        payment = Payment(
            party_type="customer",
            party_id=customer_id,
            linked_txn_id=order.order_id,
            amount=Decimal(advance_received_now),
            date=order_date,
            status="paid",
            mode="partial" if Decimal(advance_received_now) < amount else "full",
        )
        session.add(payment)

    session.commit()
    return order
