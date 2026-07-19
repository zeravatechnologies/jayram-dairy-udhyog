"""Payment lookup helpers, used by the ledger view to show what's been
paid against each individual delivery — not just the overall balance.
"""
from decimal import Decimal
from sqlalchemy import select, func

from app.models.payment import Payment
from app.models.vendor import Vendor
from app.models.customer import Customer


def record_payment(
    session,
    party_type: str,
    party_id: int,
    amount: Decimal,
    date,
    mode: str = "advance",
    status: str = "paid",
    linked_txn_id: int | None = None,
) -> Payment:
    """Record a standalone payment — used by the Payments screen, for
    payments made independent of creating a delivery/order at the same
    moment (e.g. settling an old balance, a scheduled installment).

    Validates the party actually exists, since a typo'd party_id would
    otherwise silently create an orphaned payment that never shows up
    anywhere.
    """
    if party_type not in ("vendor", "customer"):
        raise ValueError("party_type must be 'vendor' or 'customer'")
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    if party_type == "vendor":
        party = session.get(Vendor, party_id)
    else:
        party = session.get(Customer, party_id)
    if party is None:
        raise ValueError(f"No such {party_type}: {party_id}")

    payment = Payment(
        party_type=party_type, party_id=party_id, linked_txn_id=linked_txn_id,
        amount=amount, date=date, status=status, mode=mode,
    )
    session.add(payment)
    session.commit()
    return payment


def get_amount_paid_for_txn(session, txn_id: int, party_type: str) -> Decimal:
    """Amount paid against a specific transaction (a vendor delivery or
    a customer order). party_type is REQUIRED — vendor transactions and
    orders have independent ID sequences, so linked_txn_id alone isn't
    unique; without this filter a vendor delivery #1 and an order #1
    could incorrectly show each other's payments.
    """
    q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.linked_txn_id == txn_id, Payment.party_type == party_type
    )
    return Decimal(session.execute(q).scalar_one())


def get_txn_status(amount_due: Decimal, amount_paid: Decimal) -> str:
    """Returns 'paid', 'partial', or 'pending' for display purposes.

    This is a DERIVED, display-only label — it is never stored, per the
    transaction-first model (architecture doc Section 6). Recomputed
    fresh every time the ledger is drawn.
    """
    if amount_paid <= 0:
        return "pending"
    if amount_paid >= amount_due:
        return "paid"
    return "partial"


def list_recent_payments(session, limit: int = 20):
    """Recent payments across both vendors and customers, with the
    party's display name resolved — used by the Payments screen and
    the dashboard's recent-activity feed.
    """
    payments = session.execute(
        select(Payment).order_by(Payment.date.desc(), Payment.payment_id.desc()).limit(limit)
    ).scalars().all()

    results = []
    for p in payments:
        if p.party_type == "vendor":
            party = session.get(Vendor, p.party_id)
        else:
            party = session.get(Customer, p.party_id)
        party_name = party.name if party else f"(deleted {p.party_type} #{p.party_id})"
        results.append((p, party_name))
    return results
