"""CSV export of an account's history for the accounting team."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from .ledger import Ledger
from .money import format_amount
from .timeutil import iso_utc

HEADER = ["timestamp", "kind", "ref", "amount", "currency", "balance"]


def export_csv(ledger: Ledger, account_id: str) -> str:
    account = ledger.accounts[account_id]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    balance = Decimal(0)
    for entry in ledger.entries_for(account_id):
        balance += entry.delta
        writer.writerow([
            iso_utc(entry.at),
            entry.kind,
            entry.ref,
            format_amount(entry.delta, account.currency),
            account.currency,
            format_amount(balance, account.currency),
        ])
    return out.getvalue()
