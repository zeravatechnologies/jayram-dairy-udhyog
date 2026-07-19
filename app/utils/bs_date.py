"""Bikram Sambat calendar boundary for the application.

Business dates stay as Gregorian ``datetime.date`` values in storage and
services.  Only this module converts them to and from user-facing BS dates.
"""
from datetime import date, datetime, timedelta, timezone

import nepali_datetime

_DEVANAGARI_DIGITS = str.maketrans("0123456789", "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f")
_ASCII_DIGITS = str.maketrans("\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f", "0123456789")

BS_MONTHS_NP = (
    "\u092c\u0948\u0936\u093e\u0916", "\u091c\u0947\u0920", "\u0906\u0937\u093e\u0922",
    "\u0936\u094d\u0930\u093e\u0935\u0923", "\u092d\u0926\u094c", "\u0906\u0936\u094d\u0935\u093f\u0928",
    "\u0915\u093e\u0930\u094d\u0924\u093f\u0915", "\u092e\u0902\u0938\u093f\u0930", "\u092a\u0941\u0937",
    "\u092e\u093e\u0918", "\u092b\u093e\u0932\u094d\u0917\u0941\u0928", "\u091a\u0948\u0924",
)
BS_MIN_YEAR = nepali_datetime.date.min.year
BS_MAX_YEAR = nepali_datetime.date.max.year
NEPAL_TIMEZONE = timezone(timedelta(hours=5, minutes=45), name="Asia/Kathmandu")


def today_in_nepal(now: datetime | None = None) -> date:
    """Return the current Nepal civil date, independent of Windows timezone."""
    if now is None:
        return datetime.now(NEPAL_TIMEZONE).date()
    if now.tzinfo is None:
        raise ValueError("The supplied time must include a timezone")
    return now.astimezone(NEPAL_TIMEZONE).date()


def to_bs_date(ad_date: date) -> nepali_datetime.date:
    """Convert a canonical AD date to a validated BS date."""
    _require_date(ad_date)
    try:
        return nepali_datetime.date.from_datetime_date(ad_date)
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise ValueError("Date is outside the supported Nepali calendar range") from error


def bs_to_ad(year: int | str, month: int | str, day: int | str) -> date:
    """Convert BS components, including Devanagari digits, to an AD date."""
    normalized_year = _normalize_integer(year, "year")
    normalized_month = _normalize_integer(month, "month")
    normalized_day = _normalize_integer(day, "day")
    try:
        return nepali_datetime.date(
            normalized_year, normalized_month, normalized_day
        ).to_datetime_date()
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise ValueError("Invalid Bikram Sambat date") from error


def days_in_bs_month(year: int | str, month: int | str) -> int:
    """Return the number of valid days in a BS month."""
    normalized_year = _normalize_integer(year, "year")
    normalized_month = _normalize_integer(month, "month")
    for day in range(32, 28, -1):
        try:
            bs_to_ad(normalized_year, normalized_month, day)
            return day
        except ValueError:
            continue
    raise ValueError("Invalid Bikram Sambat month")


def to_bs_display(ad_date: date) -> str:
    """Convert a Python date to a Nepali-numeral BS display string, e.g. 'आषाढ ३०, २०८३'."""
    bs = to_bs_date(ad_date)
    month_name = BS_MONTHS_NP[bs.month - 1]
    day = str(bs.day).translate(_DEVANAGARI_DIGITS)
    year = str(bs.year).translate(_DEVANAGARI_DIGITS)
    return f"{month_name} {day}, {year}"


def to_devanagari_number(value) -> str:
    """Render any number/Decimal with Devanagari digits, e.g. Decimal('239.46') -> '२३९.४६'."""
    return str(value).translate(_DEVANAGARI_DIGITS)


def _normalize_integer(value: int | str, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"BS {field_name} must be a number")
    try:
        normalized = str(value).strip().translate(_ASCII_DIGITS)
        return int(normalized)
    except (TypeError, ValueError) as error:
        raise ValueError(f"BS {field_name} must be a number") from error


def _require_date(value: date) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError("Expected a datetime.date value")
