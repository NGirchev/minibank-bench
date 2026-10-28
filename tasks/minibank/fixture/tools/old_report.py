"""Nightly totals for the external partner report (owned by the partner team).

Their parser depends on the exact numbers this prints; see ADR-5.
"""
import sys

from minibank.fx_legacy import convert_amount


def usd_totals(ledger):
    totals = {}
    for acc in ledger.accounts.values():
        totals[acc.id] = convert_amount(ledger.balance(acc.id), acc.currency, "USD", ledger.rates)
    return totals


if __name__ == "__main__":
    sys.exit("run from the partner pipeline")
