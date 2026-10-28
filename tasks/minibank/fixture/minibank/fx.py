"""Exchange rates and conversion (ADR-3, ADR-5).

A rate is stored as the number of quote-currency units per one base-currency
unit, effective from a UTC instant until the next rate for the same pair.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .money import Money

PIVOT = "USD"


@dataclass(frozen=True)
class Rate:
    base: str
    quote: str
    value: Decimal
    effective_from: datetime


class RateTable:
    def __init__(self):
        self._rates: dict[tuple[str, str], list[Rate]] = {}

    def add(self, base: str, quote: str, value: Decimal | str, effective_from: datetime) -> Rate:
        if effective_from.tzinfo is None:
            raise ValueError("effective_from must be timezone-aware")
        rate = Rate(base, quote, Decimal(value), effective_from)
        series = self._rates.setdefault((base, quote), [])
        series.append(rate)
        series.sort(key=lambda r: r.effective_from)
        return rate

    def correct(self, base: str, quote: str, effective_from: datetime, value: Decimal | str) -> None:
        """Replace a published rate. Already posted amounts are not affected (ADR-7)."""
        series = self._rates.get((base, quote), [])
        for i, rate in enumerate(series):
            if rate.effective_from == effective_from:
                series[i] = Rate(base, quote, Decimal(value), effective_from)
                return
        raise LookupError(f"no {base}/{quote} rate effective from {effective_from}")

    def _direct(self, base: str, quote: str, at: datetime) -> Decimal | None:
        series = self._rates.get((base, quote))
        if not series:
            return None
        i = bisect_right([r.effective_from for r in series], at)
        return series[i - 1].value if i else None

    def rate(self, base: str, quote: str, at: datetime) -> Decimal:
        """Quote units per one base unit at instant `at`."""
        if base == quote:
            return Decimal(1)
        direct = self._direct(base, quote, at)
        if direct is not None:
            return direct
        inverse = self._direct(quote, base, at)
        if inverse is not None:
            return Decimal(1) / inverse
        if PIVOT not in (base, quote):
            return self.rate(base, PIVOT, at) * self.rate(PIVOT, quote, at)
        raise LookupError(f"no rate {base}/{quote} at {at}")


def convert(amount: Money, to: str, table: RateTable, at: datetime) -> Money:
    """Convert at the rate effective at `at`. The result is not rounded; posting rounds it."""
    return Money(amount.amount * table.rate(amount.currency, to, at), to)
