# Architecture decisions

## ADR-1 Accounts hold one currency

Every account has exactly one currency, fixed at opening. All postings on an
account are in that currency.

## ADR-2 Instants are UTC

Every timestamp stored or accepted by minibank is a timezone-aware datetime.
Business rules that talk about days or months mean UTC calendar days and
months, never the server's local time.

## ADR-3 Money is Decimal, rounded once

Amounts are `decimal.Decimal`, never `float`. Rounding is half to even, to the
currency's minor units (`money.MINOR_UNITS`: JPY has none, KWD has three).
Conversion results are rounded exactly once, when they are posted.

## ADR-4 Rates

A rate is quote units per one base unit, effective from a UTC instant until
the next rate of the same pair. Missing pairs use the inverse pair or a cross
rate through USD. Rates can be corrected after publication with
`RateTable.correct`.

## ADR-5 Legacy conversion helpers

`minibank/fx_legacy.py` predates ADR-3 and ADR-4: it uses floats, always the
newest rate and two decimals. It is deprecated; new code must use
`minibank/fx.py`. The module stays, unchanged, because `tools/old_report.py`
feeds an external partner whose parser depends on its exact output; that job
is migrated by the partner team, not here. Do not change `fx_legacy`'s
behaviour.

## ADR-6 Transfer fees

A transfer between different owners costs 0.5 % of the amount, at least the
currency's minimum fee, charged in the source currency as a separate posting.
Transfers between accounts of the same owner are free.

## ADR-7 Postings are the source of truth

A posting (`ledger.Entry`) records the exact amount that moved on an account.
Anything that shows account history — statements, exports, reports — must
show posted amounts and must not recompute them from rates, because rates can
be corrected later and a correction never changes money that already moved.
Each posting is shown as its own line.

## ADR-8 Statements

A monthly statement covers one UTC calendar month. Its opening balance is the
balance before the first instant of the month, its closing balance is the
opening balance plus every line, and the closing balance equals the account
balance at the end of the month.

## ADR-9 CSV export

The export lists every posting of the account in order, one row each:
timestamp in ISO 8601 UTC with a `Z` suffix (`2026-03-31T23:30:00Z`), kind,
reference, amount and running balance formatted with the currency's minor
units (`money.format_amount`), and the currency code. The header row is fixed;
the accounting team's import depends on it.
