"""Currency conversion helpers.

Use convert_amount() for all conversions in reports and exports: it always
returns a plain number rounded to cents, which is what the UI expects.
"""
from __future__ import annotations

from datetime import datetime, timezone

_FAR_FUTURE = datetime(9999, 1, 1, tzinfo=timezone.utc)


def rate_for(table, a: str, b: str) -> float:
    """How many units of `a` one unit of `b` buys, at the current rate."""
    return float(table.rate(b, a, _FAR_FUTURE))


def convert_amount(amount, from_currency: str, to_currency: str, table) -> float:
    if from_currency == to_currency:
        return round(float(amount), 2)
    return round(float(amount) / rate_for(table, from_currency, to_currency), 2)
