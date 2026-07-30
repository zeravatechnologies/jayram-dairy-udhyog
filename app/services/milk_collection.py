"""Milk collection service.

Entry point the UI calls to record one delivery. Named and shaped like
an API endpoint on purpose — see architecture doc Section 5 (Extension
Points): this is what lets a future web/mobile layer reuse the exact
same logic without touching it.
"""
from datetime import date as date_type, datetime
from decimal import Decimal

from app.models.payment import Payment
from app.models.transaction import RawMaterialTransaction
from app.models.vendor import Vendor
from app.services.payments import list_payments_for_txn
from app.services.pricing import calculate_milk_amount
from app.services.production import get_pool_available

VALID_SESSIONS = frozenset({"morning", "evening", "advance"})


def _normalize_date(value) -> date_type:
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, date_type):
        raise ValueError("Collection date must be a valid date")
    return value


def _normalize_session(session_label: str) -> str:
    label = (session_label or "morning").strip().lower()
    if label not in VALID_SESSIONS:
        raise ValueError("Session must be morning, evening, or advance")
    return label


def _price_delivery(vendor, quantity_l, fat_pct, manual_rate):
    quantity_l = Decimal(quantity_l)
    if quantity_l <= 0:
        raise ValueError("Quantity must be greater than zero")

    if manual_rate is not None:
        if Decimal(manual_rate) < 0:
            raise ValueError("Rate cannot be negative")
        rate_applied = Decimal(manual_rate)
        amount = (quantity_l * rate_applied).quantize(Decimal("0.01"))
        return quantity_l, None, rate_applied, amount

    rate_applied, amount = calculate_milk_amount(quantity_l, fat_pct, vendor)
    fat_value = Decimal(fat_pct) if fat_pct is not None else None
    return quantity_l, fat_value, rate_applied, amount


def _assert_pool_allows_qty_change(session, old_qty: Decimal, new_qty: Decimal) -> None:
    """Reject reductions that would make the derived raw-milk pool negative."""
    reduction = Decimal(old_qty) - Decimal(new_qty)
    if reduction <= 0:
        return
    pool_available = get_pool_available(session)
    if reduction > pool_available:
        raise ValueError(
            f"Cannot reduce quantity: that would leave the raw milk pool short "
            f"(need {reduction}L free, only {pool_available}L available). "
            f"Adjust production batches first, or reduce by less."
        )


def _sync_linked_vendor_payment(session, txn, amount_paid_now) -> None:
    """Keep the on-the-spot payment row in sync with the edited paid-now amount."""
    linked = list(list_payments_for_txn(session, txn.txn_id, party_type="vendor"))
    paid = Decimal(amount_paid_now) if amount_paid_now is not None else Decimal("0")

    if paid <= 0:
        for payment in linked:
            session.delete(payment)
        return

    mode = "partial" if paid < Decimal(txn.amount) else "full"
    if linked:
        primary = linked[0]
        primary.amount = paid
        primary.date = txn.date
        primary.mode = mode
        primary.status = "paid"
        for extra in linked[1:]:
            session.delete(extra)
    else:
        session.add(
            Payment(
                party_type="vendor",
                party_id=txn.vendor_id,
                linked_txn_id=txn.txn_id,
                amount=paid,
                date=txn.date,
                status="paid",
                mode=mode,
            )
        )


def record_milk_collection(
    session,
    vendor_id: int,
    date: date_type,
    quantity_l: Decimal,
    fat_pct: Decimal | None = None,
    session_label: str = "morning",
    amount_paid_now: Decimal | None = None,
    manual_rate: Decimal | None = None,
) -> RawMaterialTransaction:
    """Record one milk delivery, and optionally an on-the-spot payment.

    manual_rate: if provided, overrides the auto-computed rate entirely —
    this is the "negotiated price, one-off" case (proposal Section 5.2):
    a one-time override never changes the vendor's standing default rate,
    it only applies to this single transaction.

    Returns the created transaction. Raises ValueError on bad input
    (e.g. negative quantity, unknown vendor) rather than failing silently —
    the UI layer is responsible for turning that into a friendly message
    (see deployment doc Section 7.3, error handling philosophy).
    """
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise ValueError(f"No such vendor: {vendor_id}")
    if quantity_l is None or Decimal(quantity_l) <= 0:
        raise ValueError("Quantity must be greater than zero")

    date = _normalize_date(date)
    label = _normalize_session(session_label)
    quantity_l, fat_value, rate_applied, amount = _price_delivery(
        vendor, quantity_l, fat_pct, manual_rate
    )

    txn = RawMaterialTransaction(
        vendor_id=vendor_id,
        date=date,
        session=label,
        quantity_l=quantity_l,
        fat_pct=fat_value,
        rate_applied=rate_applied,
        amount=amount,
    )
    session.add(txn)
    session.flush()  # get txn.txn_id before we may link a payment to it

    if amount_paid_now is not None and Decimal(amount_paid_now) > 0:
        payment = Payment(
            party_type="vendor",
            party_id=vendor_id,
            linked_txn_id=txn.txn_id,
            amount=Decimal(amount_paid_now),
            date=date,
            status="paid",
            mode="partial" if Decimal(amount_paid_now) < amount else "full",
        )
        session.add(payment)

    session.commit()
    return txn


def get_milk_collection(session, txn_id: int) -> RawMaterialTransaction | None:
    return session.get(RawMaterialTransaction, txn_id)


def update_milk_collection(
    session,
    txn_id: int,
    date: date_type,
    quantity_l: Decimal,
    fat_pct: Decimal | None = None,
    session_label: str = "morning",
    amount_paid_now: Decimal | None = None,
    manual_rate: Decimal | None = None,
) -> RawMaterialTransaction:
    """Correct an existing milk delivery in place.

    Recalculates rate/amount, syncs the linked paid-now payment, and
    rejects quantity reductions that would make the raw-milk pool negative.
    """
    txn = session.get(RawMaterialTransaction, txn_id)
    if txn is None:
        raise ValueError(f"No such milk collection: {txn_id}")

    vendor = session.get(Vendor, txn.vendor_id)
    if vendor is None:
        raise ValueError(f"No such vendor: {txn.vendor_id}")

    date = _normalize_date(date)
    label = _normalize_session(session_label)
    new_qty, fat_value, rate_applied, amount = _price_delivery(
        vendor, quantity_l, fat_pct, manual_rate
    )

    _assert_pool_allows_qty_change(session, Decimal(txn.quantity_l), new_qty)

    txn.date = date
    txn.session = label
    txn.quantity_l = new_qty
    txn.fat_pct = fat_value
    txn.rate_applied = rate_applied
    txn.amount = amount

    _sync_linked_vendor_payment(session, txn, amount_paid_now)
    session.commit()
    return txn


def delete_milk_collection(session, txn_id: int) -> None:
    """Remove a milk delivery and its linked vendor payments.

    Rejected when deleting the quantity would make the raw-milk pool negative.
    """
    txn = session.get(RawMaterialTransaction, txn_id)
    if txn is None:
        raise ValueError(f"No such milk collection: {txn_id}")

    _assert_pool_allows_qty_change(session, Decimal(txn.quantity_l), Decimal("0"))

    for payment in list_payments_for_txn(session, txn.txn_id, party_type="vendor"):
        session.delete(payment)
    session.delete(txn)
    session.commit()
