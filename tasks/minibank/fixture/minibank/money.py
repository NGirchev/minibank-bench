"""Money values and currency rules (ADR-3)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

MINOR_UNITS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0, "KWD": 3}


def minor_units(currency: str) -> int:
    try:
        return MINOR_UNITS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency}") from None


def quantize(amount: Decimal, currency: str) -> Decimal:
    """Round to the currency's minor units, half to even."""
    exponent = Decimal(1).scaleb(-minor_units(currency))
    return amount.quantize(exponent, rounding=ROUND_HALF_EVEN)


def format_amount(amount: Decimal, currency: str) -> str:
    """Render an amount with exactly the currency's minor units: '1500', '12.345', '-3.10'."""
    return f"{quantize(amount, currency):f}"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money.amount must be a Decimal")
        minor_units(self.currency)

    def _same(self, other: Money) -> None:
        if not isinstance(other, Money) or other.currency != self.currency:
            raise ValueError("currency mismatch")

    def __add__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def rounded(self) -> Money:
        return Money(quantize(self.amount, self.currency), self.currency)

    def __str__(self) -> str:
        return f"{format_amount(self.amount, self.currency)} {self.currency}"


def money(value: str | int | Decimal, currency: str) -> Money:
    if isinstance(value, float):
        raise TypeError("use str or Decimal for money, never float")
    return Money(Decimal(value), currency)
