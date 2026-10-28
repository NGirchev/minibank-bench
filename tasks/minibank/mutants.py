"""Plausible wrong fixes, injected into the reference solution.

Each one is a fix a model could stop at. The agent's own tests should catch
them. Entry: name -> (file inside the package, old text, new text).
"""

_LINES = '''    lines = [Line(entry.at, entry.kind, entry.ref, entry.delta, describe(entry, ledger))
             for entry in ledger.entries_for(account_id) if start <= entry.at < end]'''


def _loop(transfer_in: str, merge_fee: bool = False) -> str:
    fee = ('''        if entry.kind == "fee":
            continue
        if entry.kind == "transfer_out":
            transfer = ledger.transfers[entry.ref]
            amount = -(transfer.amount.amount + transfer.fee)
        el''' if merge_fee else "        ")
    return f'''    lines = []
    for entry in ledger.entries_for(account_id):
        if not start <= entry.at < end:
            continue
{fee}if entry.kind == "transfer_in":
            transfer = ledger.transfers[entry.ref]
            amount = {transfer_in}
        else:
            amount = entry.delta
        lines.append(Line(entry.at, entry.kind, entry.ref, amount, describe(entry, ledger)))'''


_LEGACY = ('__import__("decimal").Decimal(str(__import__("minibank.fx_legacy", fromlist=["x"]).convert_amount('
           'transfer.amount.amount, transfer.amount.currency, account.currency, ledger.rates)))')
_RECOMPUTE = ('__import__("minibank.fx", fromlist=["x"]).convert('
              'transfer.amount, account.currency, ledger.rates, transfer.at).rounded().amount')

_EXPORT_LOOP = '''        balance += entry.delta'''


def _export_amount(expr: str) -> str:
    return f'''        if entry.kind == "transfer_in":
            transfer = ledger.transfers[entry.ref]
            entry = __import__("dataclasses").replace(entry, delta={expr})
        balance += entry.delta'''


MUTANTS = {
    "statement_legacy_conversion": ("statement.py", _LINES, _loop(_LEGACY)),
    "statement_recomputes_with_new_fx": ("statement.py", _LINES, _loop(_RECOMPUTE)),
    "statement_fee_merged_into_transfer": ("statement.py", _LINES, _loop("entry.delta", merge_fee=True)),
    "statement_local_month": (
        "statement.py",
        "    start, end = month_bounds_utc(year, month)",
        "    start, end = __import__('minibank.timeutil', fromlist=['x']).month_bounds(year, month)",
    ),
    "statement_boundary_inclusive_end": (
        "statement.py", "if start <= entry.at < end]", "if start < entry.at <= end]",
    ),
    "export_legacy_conversion": ("export.py", _EXPORT_LOOP, _export_amount(_LEGACY.replace("account.currency", "account.currency"))),
    "export_recomputes_with_new_fx": ("export.py", _EXPORT_LOOP, _export_amount(_RECOMPUTE)),
    "export_two_decimals": (
        "export.py",
        "            format_amount(entry.delta, account.currency),",
        '            f"{entry.delta:.2f}",',
    ),
    "export_local_time": (
        "export.py",
        "            iso_utc(entry.at),",
        '            entry.at.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ"),',
    ),
}
