"""Milk pricing calculation.

This is the highest-risk piece of logic in the whole application — a
subtle bug here costs the owner real money on every single delivery.
Kept as pure, dependency-free functions so they're trivial to unit test
in isolation, per architecture doc Section 7.1.
"""
from decimal import Decimal, ROUND_HALF_UP


TWO_PLACES = Decimal("0.01")


def calculate_milk_amount(quantity_l: Decimal, fat_pct: Decimal | None, vendor) -> tuple[Decimal, Decimal]:
    """Calculate (rate_applied, amount) for one milk delivery.

    - fat_based mode: rate = fat_pct * vendor.default_rate  (the fat-price rate)
    - flat_rate mode: rate = vendor.default_rate directly

    Matches the formula confirmed against the owner's paper ledger
    (image 7 in the discovery photos): Milk Rate = Fat% x Fat Price Rate.
    """
    quantity_l = Decimal(quantity_l)
    default_rate = Decimal(vendor.default_rate)

    if vendor.pricing_mode == "fat_based":
        if fat_pct is None:
            raise ValueError("fat_pct is required for a fat_based vendor")
        rate_applied = (Decimal(fat_pct) * default_rate).quantize(Decimal("0.0001"))
    elif vendor.pricing_mode == "flat_rate":
        rate_applied = default_rate
    else:
        raise ValueError(f"Unknown pricing_mode: {vendor.pricing_mode!r}")

    amount = (quantity_l * rate_applied).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return rate_applied, amount
