# minibank

A small multi-currency ledger: accounts in one currency each, deposits,
withdrawals, transfers with conversion and fees, monthly statements, CSV
export and a few back-office reports. Pure Python, standard library only.

- `minibank/money.py` — `Money`, currency minor units, rounding, formatting
- `minibank/fx.py` — exchange-rate table and conversion
- `minibank/ledger.py` — accounts, postings, transfers, balances
- `minibank/statement.py` — monthly statements
- `minibank/export.py` — CSV export for accounting
- `minibank/reports.py` — back-office summaries
- `tools/old_report.py` — partner report job

Design decisions are recorded in `DECISIONS.md`.

Run the tests with `python3 -m unittest`.
