from datetime import date, datetime, timezone

import pytest

from app.utils.bs_date import (
    BS_MAX_YEAR,
    BS_MIN_YEAR,
    bs_to_ad,
    days_in_bs_month,
    to_bs_date,
    to_bs_display,
    today_in_nepal,
)


def test_known_ad_date_converts_to_bikram_sambat():
    bs_date = to_bs_date(date(2026, 7, 18))

    assert (bs_date.year, bs_date.month, bs_date.day) == (2083, 4, 2)
    assert to_bs_display(date(2026, 7, 18)) == "श्रावण २, २०८३"


def test_nepali_new_year_converts_to_ad():
    assert bs_to_ad(2083, 1, 1) == date(2026, 4, 14)


def test_bs_conversion_accepts_devanagari_digits():
    assert bs_to_ad("२०८३", "१", "१") == date(2026, 4, 14)


def test_bs_round_trip_preserves_business_date():
    original = date(2026, 7, 18)
    bs_date = to_bs_date(original)

    assert bs_to_ad(bs_date.year, bs_date.month, bs_date.day) == original


def test_invalid_bs_day_is_rejected():
    month_days = days_in_bs_month(2083, 1)

    with pytest.raises(ValueError, match="Invalid Bikram Sambat date"):
        bs_to_ad(2083, 1, month_days + 1)


def test_supported_bs_range_boundaries_round_trip():
    minimum_ad = bs_to_ad(BS_MIN_YEAR, 1, 1)
    maximum_ad = bs_to_ad(BS_MAX_YEAR, 12, 30)

    assert to_bs_date(minimum_ad).year == BS_MIN_YEAR
    assert to_bs_date(maximum_ad).year == BS_MAX_YEAR


def test_date_outside_supported_bs_range_is_rejected():
    with pytest.raises(ValueError, match="Invalid Bikram Sambat date"):
        bs_to_ad(BS_MIN_YEAR - 1, 12, 30)


def test_nepal_today_uses_nepal_civil_timezone():
    utc_time = datetime(2026, 7, 18, 19, 0, tzinfo=timezone.utc)

    assert today_in_nepal(utc_time) == date(2026, 7, 19)


def test_nepal_today_rejects_ambiguous_naive_time():
    with pytest.raises(ValueError, match="timezone"):
        today_in_nepal(datetime(2026, 7, 18, 19, 0))


def test_datetime_is_not_accepted_as_business_date():
    with pytest.raises(TypeError, match="datetime.date"):
        to_bs_date(datetime(2026, 7, 18, tzinfo=timezone.utc))
