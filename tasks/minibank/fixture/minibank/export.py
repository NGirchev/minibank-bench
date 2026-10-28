"""CSV export of an account's history for the accounting team."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from .fx_legacy import convert_amount
from .ledger import Ledger

HEADER = ["timestamp", "kind", "ref", "amount", "currency", "balance"]


def export_csv(ledger: Ledger, account_id: str) -> str:
    account = ledger.accounts[account_id]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    balance = Decimal(0)
    for entry in ledger.entries_for(account_id):
        amount = entry.delta
        if entry.kind == "transfer_in":
            transfer = ledger.transfers[entry.ref]
            amount = Decimal(str(convert_amount(transfer.amount.amount, transfer.amount.currency,
                                                account.currency, ledger.rates)))
        balance += amount
        writer.writerow([
            entry.at.astimezone().strftime("%Y-%m-%d %H:%M"),
            entry.kind,
            entry.ref,
            f"{amount:.2f}",
            account.currency,
            f"{balance:.2f}",
        ])
    return out.getvalue()
