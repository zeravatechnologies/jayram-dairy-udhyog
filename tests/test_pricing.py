"""Tests for app.services.pricing — the highest-risk logic in the app.

Verifies the fat-based formula against the real example confirmed from
the owner's paper ledger (fat% x fat_price_rate x quantity), plus the
flat-rate path and edge cases that would otherwise silently cost money.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.pricing import calculate_milk_amount


def make_vendor(pricing_mode, default_rate):
    return SimpleNamespace(pricing_mode=pricing_mode, default_rate=default_rate)


def test_fat_based_pricing_matches_ledger_example():
    # From the wireframe example: fat 6.2 x rate 9.42 = 58.4/L, x 4.1L = 239.44
    vendor = make_vendor("fat_based", Decimal("9.42"))
    rate, amount = calculate_milk_amount(Decimal("4.1"), Decimal("6.2"), vendor)
    assert rate == Decimal("58.4040")
    assert amount == Decimal("239.46")  # 4.1 * 58.4040, rounded to 2dp


def test_flat_rate_pricing_ignores_fat():
    vendor = make_vendor("flat_rate", Decimal("58.00"))
    rate, amount = calculate_milk_amount(Decimal("3.1"), None, vendor)
    assert rate == Decimal("58.00")
    assert amount == Decimal("179.80")


def test_fat_based_requires_fat_pct():
    vendor = make_vendor("fat_based", Decimal("9.42"))
    with pytest.raises(ValueError, match="fat_pct is required"):
        calculate_milk_amount(Decimal("4.0"), None, vendor)


def test_unknown_pricing_mode_raises():
    vendor = make_vendor("something_else", Decimal("10"))
    with pytest.raises(ValueError, match="Unknown pricing_mode"):
        calculate_milk_amount(Decimal("4.0"), Decimal("6.0"), vendor)


def test_zero_fat_gives_zero_amount_not_an_error():
    # Zero fat is unusual but not invalid — should compute to zero, not crash.
    vendor = make_vendor("fat_based", Decimal("9.42"))
    rate, amount = calculate_milk_amount(Decimal("5.0"), Decimal("0"), vendor)
    assert rate == Decimal("0.0000")
    assert amount == Decimal("0.00")


def test_rounding_half_up_on_amount():
    # amount rounding must be predictable (half-up), not banker's rounding,
    # so it matches how the owner rounds by hand.
    vendor = make_vendor("flat_rate", Decimal("58.375"))
    rate, amount = calculate_milk_amount(Decimal("1"), None, vendor)
    assert amount == Decimal("58.38")  # 58.375 rounds up, not to 58.37 or 58.38-even
