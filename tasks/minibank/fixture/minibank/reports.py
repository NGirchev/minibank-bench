"""Small reports for the back office."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .ledger import Ledger
from .money import format_amount


def account_summary(ledger: Ledger) -> dict[str, str]:
    """Current balance of every account, formatted: {'acc-1': '120.50 USD'}."""
    return {acc.id: f"{format_amount(ledger.balance(acc.id), acc.currency)} {acc.currency}"
            for acc in ledger.accounts.values()}


def fees_by_currency(ledger: Ledger) -> dict[str, str]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for entry in ledger.entries:
        if entry.kind == "fee":
            totals[entry.currency] += -entry.delta
    return {cur: format_amount(total, cur) for cur, total in sorted(totals.items())}
