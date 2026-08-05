"""Order service — the customer-side mirror of milk_collection.py.

Immediate sales require finished-goods stock and decrement it on create.
Advance bookings (delivery_date after order_date) reserve without stock
until mark-delivered. Cancelled orders never touch stock.
"""
from datetime import date as date_type, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.customer import Customer
from app.models.order import OrderTransaction
from app.models.payment import Payment
from app.models.product import Product
from app.utils.bs_date import today_in_nepal


def _is_advance_order(order_date: date_type, delivery_date: date_type | None) -> bool:
    return delivery_date is not None and delivery_date > order_date


def create_order(
    session,
    customer_id: int,
    product_id: int,
    order_date: date_type,
    quantity: Decimal,
    rate: Decimal,
    delivery_date: date_type | None = None,
    advance_received_now: Decimal | None = None,
    planning_note: str | None = None,
) -> OrderTransaction:
    """Create an order. Immediate sales decrement stock; advance bookings
    (future delivery_date) do not until deliver_order is called.
    """
    if isinstance(order_date, datetime):
        order_date = order_date.date()
    if not isinstance(order_date, date_type):
        raise ValueError("Order date must be a valid date")
    if delivery_date is not None:
        if isinstance(delivery_date, datetime):
            delivery_date = delivery_date.date()
        if not isinstance(delivery_date, date_type):
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

    is_advance = _is_advance_order(order_date, delivery_date)
    if not is_advance and quantity > Decimal(product.current_stock):
        raise ValueError(
            f"Not enough stock: ordering {quantity} {product.unit}, "
            f"only {product.current_stock} {product.unit} in stock"
        )

    note = (planning_note or "").strip() or None
    amount = (quantity * rate).quantize(Decimal("0.01"))
    status = "placed" if is_advance else "delivered"

    order = OrderTransaction(
        customer_id=customer_id,
        product_id=product_id,
        order_date=order_date,
        delivery_date=delivery_date,
        quantity=quantity,
        rate=rate,
        amount=amount,
        status=status,
        planning_note=note,
    )
    session.add(order)
    session.flush()

    if not is_advance:
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


def _sync_linked_customer_payment(session, order, advance_received_now) -> None:
    """Keep the advance payment row in sync with the edited advance amount."""
    from app.services.payments import list_payments_for_txn

    linked = list(list_payments_for_txn(session, order.order_id, party_type="customer"))
    paid = Decimal(advance_received_now) if advance_received_now is not None else Decimal("0")

    if paid <= 0:
        for payment in linked:
            session.delete(payment)
        return

    mode = "partial" if paid < Decimal(order.amount) else "full"
    if linked:
        primary = linked[0]
        primary.amount = paid
        primary.date = order.order_date
        primary.mode = mode
        primary.status = "paid"
        for extra in linked[1:]:
            session.delete(extra)
    else:
        session.add(
            Payment(
                party_type="customer",
                party_id=order.customer_id,
                linked_txn_id=order.order_id,
                amount=paid,
                date=order.order_date,
                status="paid",
                mode=mode,
            )
        )


def update_placed_order(
    session,
    order_id: int,
    quantity: Decimal,
    rate: Decimal,
    delivery_date: date_type | None = None,
    planning_note: str | None = None,
    advance_received_now: Decimal | None = None,
    product_id: int | None = None,
) -> OrderTransaction:
    """Correct a placed advance order before delivery. Stock is untouched."""
    order = session.get(OrderTransaction, order_id)
    if order is None:
        raise ValueError(f"No such order: {order_id}")
    if order.status != "placed":
        raise ValueError("Only placed advance orders can be edited")

    if delivery_date is not None:
        if isinstance(delivery_date, datetime):
            delivery_date = delivery_date.date()
        if not isinstance(delivery_date, date_type):
            raise ValueError("Delivery date must be a valid date")
        if delivery_date < order.order_date:
            raise ValueError("Delivery date cannot be before the order date")
        if delivery_date <= order.order_date:
            raise ValueError(
                "Edited advance orders must keep a delivery date after the order date"
            )

    quantity = Decimal(quantity)
    rate = Decimal(rate)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if rate < 0:
        raise ValueError("Rate cannot be negative")

    if product_id is not None and product_id != order.product_id:
        product = session.get(Product, product_id)
        if product is None:
            raise ValueError(f"No such product: {product_id}")
        order.product_id = product_id

    if delivery_date is not None:
        order.delivery_date = delivery_date

    order.quantity = quantity
    order.rate = rate
    order.amount = (quantity * rate).quantize(Decimal("0.01"))
    order.planning_note = (planning_note or "").strip() or None

    _sync_linked_customer_payment(session, order, advance_received_now)
    session.commit()
    return order


def deliver_order(session, order_id: int) -> OrderTransaction:
    """Fulfill a placed advance order: require stock, decrement, mark delivered."""
    order = session.get(OrderTransaction, order_id)
    if order is None:
        raise ValueError(f"No such order: {order_id}")
    if order.status == "delivered":
        raise ValueError("Order is already delivered")
    if order.status == "cancelled":
        raise ValueError("Cannot deliver a cancelled order")
    if order.status != "placed":
        raise ValueError(f"Cannot deliver order with status {order.status}")

    product = session.get(Product, order.product_id)
    if product is None:
        raise ValueError(f"No such product: {order.product_id}")

    quantity = Decimal(order.quantity)
    if quantity > Decimal(product.current_stock):
        raise ValueError(
            f"Not enough stock: need {quantity} {product.unit}, "
            f"only {product.current_stock} {product.unit} in stock"
        )

    product.current_stock = Decimal(product.current_stock) - quantity
    order.status = "delivered"
    session.commit()
    return order


def cancel_order(session, order_id: int) -> OrderTransaction:
    """Cancel a placed advance order. Stock was never taken, so nothing to restore."""
    order = session.get(OrderTransaction, order_id)
    if order is None:
        raise ValueError(f"No such order: {order_id}")
    if order.status == "cancelled":
        raise ValueError("Order is already cancelled")
    if order.status == "delivered":
        raise ValueError("Cannot cancel a delivered order")
    if order.status != "placed":
        raise ValueError(f"Cannot cancel order with status {order.status}")

    order.status = "cancelled"
    session.commit()
    return order


def delete_order(session, order_id: int) -> None:
    """Permanently remove an order and its linked customer payments.

    Restores finished-goods stock when the order was delivered (stock was
    taken). Placed and cancelled orders never touched stock.
    """
    from app.services.payments import list_payments_for_txn

    order = session.get(OrderTransaction, order_id)
    if order is None:
        raise ValueError(f"No such order: {order_id}")

    if order.status == "delivered":
        product = session.get(Product, order.product_id)
        if product is None:
            raise ValueError(f"No such product: {order.product_id}")
        product.current_stock = Decimal(product.current_stock) + Decimal(order.quantity)

    for payment in list_payments_for_txn(session, order.order_id, party_type="customer"):
        session.delete(payment)
    session.delete(order)
    session.commit()


def list_upcoming_advance_orders(session, within_days: int = 30, as_of: date_type | None = None):
    """Placed advance orders with delivery_date from as_of through as_of+within_days."""
    as_of = as_of or today_in_nepal()
    if isinstance(as_of, datetime):
        as_of = as_of.date()
    until = as_of + timedelta(days=within_days)
    return (
        session.execute(
            select(OrderTransaction)
            .options(
                joinedload(OrderTransaction.customer),
                joinedload(OrderTransaction.product),
            )
            .where(
                OrderTransaction.status == "placed",
                OrderTransaction.delivery_date.is_not(None),
                OrderTransaction.delivery_date >= as_of,
                OrderTransaction.delivery_date <= until,
            )
            .order_by(OrderTransaction.delivery_date.asc(), OrderTransaction.order_id.asc())
        )
        .scalars()
        .unique()
        .all()
    )
