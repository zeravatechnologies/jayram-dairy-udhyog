"""Milk collection service.

Entry point the UI calls to record one delivery. Named and shaped like
an API endpoint on purpose — see architecture doc Section 5 (Extension
Points): this is what lets a future web/mobile layer reuse the exact
same logic without touching it.
"""
from datetime import date as date_type
from decimal import Decimal

from app.models.transaction import RawMaterialTransaction
from app.models.vendor import Vendor
from app.models.payment import Payment
from app.services.pricing import calculate_milk_amount


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

    if manual_rate is not None:
        if Decimal(manual_rate) < 0:
            raise ValueError("Rate cannot be negative")
        rate_applied = Decimal(manual_rate)
        amount = (Decimal(quantity_l) * rate_applied).quantize(Decimal("0.01"))
    else:
        rate_applied, amount = calculate_milk_amount(quantity_l, fat_pct, vendor)

    txn = RawMaterialTransaction(
        vendor_id=vendor_id,
        date=date,
        session=session_label,
        quantity_l=Decimal(quantity_l),
        fat_pct=Decimal(fat_pct) if fat_pct is not None else None,
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
