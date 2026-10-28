"""Monthly account statements."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .fx_legacy import convert_amount
from .ledger import Entry, Ledger
from .timeutil import month_bounds

KIND_LABELS = {
    "deposit": "Deposit",
    "withdrawal": "Withdrawal",
    "transfer_out": "Transfer to",
    "transfer_in": "Transfer from",
    "fee": "Fee",
}


@dataclass(frozen=True)
class Line:
    at: datetime
    kind: str
    ref: str
    amount: Decimal
    description: str


@dataclass(frozen=True)
class Statement:
    account: str
    currency: str
    year: int
    month: int
    opening: Decimal
    closing: Decimal
    lines: list[Line]


def describe(entry: Entry, ledger: Ledger) -> str:
    label = KIND_LABELS[entry.kind]
    transfer = ledger.transfers.get(entry.ref)
    if entry.kind == "transfer_out" and transfer:
        return f"{label} {transfer.dst}"
    if entry.kind == "transfer_in" and transfer:
        return f"{label} {transfer.src}"
    return f"{label} {entry.memo}".strip()


def monthly_statement(ledger: Ledger, account_id: str, year: int, month: int) -> Statement:
    account = ledger.accounts[account_id]
    start, end = month_bounds(year, month)
    opening = ledger.balance(account_id, at=start)
    lines = []
    for entry in ledger.entries_for(account_id):
        if not start <= entry.at < end:
            continue
        if entry.kind == "fee":
            continue  # the fee is shown inside its transfer line
        if entry.kind == "transfer_out":
            transfer = ledger.transfers[entry.ref]
            amount = -(transfer.amount.amount + transfer.fee)
        elif entry.kind == "transfer_in":
            # Show the transferred amount in this account's currency.
            transfer = ledger.transfers[entry.ref]
            amount = Decimal(str(convert_amount(transfer.amount.amount, transfer.amount.currency,
                                                account.currency, ledger.rates)))
        else:
            amount = entry.delta
        lines.append(Line(entry.at, entry.kind, entry.ref, amount, describe(entry, ledger)))
    closing = opening + sum((line.amount for line in lines), Decimal(0))
    return Statement(account_id, account.currency, year, month, opening, closing, lines)
