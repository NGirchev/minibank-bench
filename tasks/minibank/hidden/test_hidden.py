"""Hidden acceptance tests for the minibank task. Never shown to the agent.

Names starting with `test_subtle_` cover conditions that need DECISIONS.md or
a second look (UTC months, rate corrections, separate fee lines, the legacy
module that must stay as it is); the grader reports them separately.
"""
import contextlib
import csv
import io
import os
import time
import unittest
from decimal import Decimal

from minibank.fx import RateTable, convert
from minibank.ledger import Ledger
from minibank.money import format_amount, money
from minibank.timeutil import utc


def month_bounds_utc(year, month):
    """UTC month bounds, computed here so the suite does not depend on the agent's timeutil helpers."""
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return utc(year, month, 1), utc(ny, nm, 1)


@contextlib.contextmanager
def local_tz(name):
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def rates():
    t = RateTable()
    t.add("USD", "EUR", "0.90", utc(2026, 1, 1))
    t.add("USD", "EUR", "0.95", utc(2026, 3, 1))
    t.add("USD", "JPY", "150", utc(2026, 1, 1))
    t.add("USD", "JPY", "160", utc(2026, 3, 1))
    t.add("USD", "KWD", "0.3071", utc(2026, 1, 1))
    t.add("USD", "KWD", "0.3080", utc(2026, 3, 1))
    return t


def bank():
    lg = Ledger(rates())
    lg.open_account("ann-usd", "USD", "ann")
    lg.open_account("ann-eur", "EUR", "ann")
    lg.open_account("bob-eur", "EUR", "bob")
    lg.open_account("cho-jpy", "JPY", "cho")
    lg.open_account("dee-kwd", "KWD", "dee")
    lg.deposit("ann-usd", money("5000", "USD"), utc(2026, 1, 2))
    lg.transfer("ann-usd", "bob-eur", money("1234.57", "USD"), utc(2026, 2, 14, 10))
    lg.transfer("ann-usd", "cho-jpy", money("333.33", "USD"), utc(2026, 2, 20, 8))
    lg.transfer("ann-usd", "dee-kwd", money("777.77", "USD"), utc(2026, 2, 27, 23, 30))
    lg.withdraw("bob-eur", money("100", "EUR"), utc(2026, 3, 5))
    lg.transfer("ann-usd", "ann-eur", money("100", "USD"), utc(2026, 3, 31, 23, 30))
    lg.transfer("ann-usd", "bob-eur", money("10", "USD"), utc(2026, 4, 1))
    return lg


def statement(lg, acc, year, month):
    from minibank.statement import monthly_statement
    return monthly_statement(lg, acc, year, month)


def export_rows(lg, acc):
    from minibank.export import export_csv
    return list(csv.reader(io.StringIO(export_csv(lg, acc))))


MONTHS = [(2026, 1), (2026, 2), (2026, 3), (2026, 4)]


class Statements(unittest.TestCase):
    def test_closing_equals_balance_every_account_and_month(self):
        lg = bank()
        for acc in lg.accounts:
            for y, m in MONTHS:
                start, end = month_bounds_utc(y, m)
                with self.subTest(acc=acc, month=m):
                    st = statement(lg, acc, y, m)
                    self.assertEqual(st.opening, lg.balance(acc, at=start))
                    self.assertEqual(st.closing, lg.balance(acc, at=end))
                    self.assertEqual(st.closing, st.opening + sum((ln.amount for ln in st.lines), Decimal(0)))

    def test_transfer_in_shows_credited_amount(self):
        lg = bank()
        credited = [t.credited.amount for t in lg.transfers.values() if t.dst == "bob-eur"]
        st = statement(lg, "bob-eur", 2026, 2)
        self.assertEqual([ln.amount for ln in st.lines], credited[:1])

    def test_lines_are_the_postings(self):
        lg = bank()
        start, end = month_bounds_utc(2026, 2)
        posted = [(e.kind, e.ref, e.delta) for e in lg.entries_for("ann-usd") if start <= e.at < end]
        st = statement(lg, "ann-usd", 2026, 2)
        self.assertEqual([(ln.kind, ln.ref, ln.amount) for ln in st.lines], posted)

    def test_subtle_fee_is_its_own_line(self):
        lg = bank()
        st = statement(lg, "ann-usd", 2026, 2)
        fees = [ln.amount for ln in st.lines if ln.kind == "fee"]
        expected = [-t.fee for t in lg.transfers.values() if t.src == "ann-usd" and t.fee and t.at.month == 2]
        self.assertEqual(fees, expected)
        outs = [ln.amount for ln in st.lines if ln.kind == "transfer_out"]
        self.assertEqual(outs, [-t.amount.amount for t in lg.transfers.values() if t.at.month == 2])

    def test_jpy_and_kwd_lines(self):
        lg = bank()
        jpy = statement(lg, "cho-jpy", 2026, 2).lines[0].amount
        kwd = statement(lg, "dee-kwd", 2026, 2).lines[0].amount
        self.assertEqual(jpy, lg.balance("cho-jpy"))
        self.assertEqual(jpy.as_tuple().exponent, 0)
        self.assertEqual(kwd, lg.balance("dee-kwd"))
        self.assertEqual(kwd.as_tuple().exponent, -3)

    def test_subtle_rate_correction_keeps_statement(self):
        lg = bank()
        before = statement(lg, "bob-eur", 2026, 2)
        lg.rates.correct("USD", "EUR", utc(2026, 1, 1), "0.80")
        lg.rates.correct("USD", "EUR", utc(2026, 3, 1), "0.70")
        after = statement(lg, "bob-eur", 2026, 2)
        self.assertEqual([ln.amount for ln in after.lines], [ln.amount for ln in before.lines])
        self.assertEqual(after.closing, lg.balance("bob-eur", at=utc(2026, 3, 1)))

    def test_empty_month(self):
        lg = bank()
        st = statement(lg, "cho-jpy", 2026, 3)
        self.assertEqual(st.lines, [])
        self.assertEqual(st.opening, st.closing)
        self.assertEqual(st.closing, lg.balance("cho-jpy"))


class Boundaries(unittest.TestCase):
    def check_boundaries(self):
        lg = bank()
        march = statement(lg, "ann-eur", 2026, 3)
        self.assertEqual([ln.at for ln in march.lines], [utc(2026, 3, 31, 23, 30)])
        april = statement(lg, "bob-eur", 2026, 4)
        self.assertEqual([ln.at for ln in april.lines], [utc(2026, 4, 1)])
        march_bob = statement(lg, "bob-eur", 2026, 3)
        self.assertEqual(march_bob.closing, lg.balance("bob-eur", at=utc(2026, 4, 1)))
        feb_dee = statement(lg, "dee-kwd", 2026, 2)
        self.assertEqual(len(feb_dee.lines), 1)

    def test_subtle_utc_months_in_tokyo(self):
        with local_tz("Asia/Tokyo"):
            self.check_boundaries()

    def test_subtle_utc_months_in_los_angeles(self):
        with local_tz("America/Los_Angeles"):
            self.check_boundaries()

    def test_utc_months_in_utc(self):
        with local_tz("UTC"):
            self.check_boundaries()


class Exports(unittest.TestCase):
    def test_header_unchanged(self):
        self.assertEqual(export_rows(bank(), "ann-usd")[0],
                         ["timestamp", "kind", "ref", "amount", "currency", "balance"])

    def test_one_row_per_posting(self):
        lg = bank()
        rows = export_rows(lg, "ann-usd")[1:]
        entries = lg.entries_for("ann-usd")
        self.assertEqual([(r[1], r[2]) for r in rows], [(e.kind, e.ref) for e in entries])

    def test_amounts_are_posted_and_formatted(self):
        lg = bank()
        for acc in lg.accounts:
            with self.subTest(acc=acc):
                rows = export_rows(lg, acc)[1:]
                cur = lg.accounts[acc].currency
                entries = lg.entries_for(acc)
                self.assertEqual([r[3] for r in rows], [format_amount(e.delta, cur) for e in entries])
                self.assertEqual({r[4] for r in rows}, {cur})

    def test_running_balance(self):
        lg = bank()
        for acc in lg.accounts:
            with self.subTest(acc=acc):
                rows = export_rows(lg, acc)[1:]
                cur = lg.accounts[acc].currency
                running, expected = Decimal(0), []
                for e in lg.entries_for(acc):
                    running += e.delta
                    expected.append(format_amount(running, cur))
                self.assertEqual([r[5] for r in rows], expected)

    def test_subtle_timestamps_iso_utc(self):
        with local_tz("Asia/Tokyo"):
            rows = export_rows(bank(), "ann-eur")[1:]
        self.assertEqual([r[0] for r in rows], ["2026-03-31T23:30:00Z"])

    def test_subtle_rate_correction_keeps_export(self):
        lg = bank()
        before = export_rows(lg, "cho-jpy")
        lg.rates.correct("USD", "JPY", utc(2026, 1, 1), "120")
        lg.rates.correct("USD", "JPY", utc(2026, 3, 1), "100")
        self.assertEqual(export_rows(lg, "cho-jpy"), before)


def legacy_expected(amount, src, dst, table):
    # The behaviour fx_legacy had when the task started (ADR-5: must not change).
    if src == dst:
        return round(float(amount), 2)
    from datetime import datetime, timezone
    far = datetime(9999, 1, 1, tzinfo=timezone.utc)
    return round(float(amount) / float(table.rate(dst, src, far)), 2)


class Untouched(unittest.TestCase):
    def test_subtle_legacy_module_behaviour_kept(self):
        from minibank import fx_legacy
        t = rates()
        for amount, src, dst in [("100", "USD", "EUR"), ("1234.57", "USD", "JPY"), ("777.77", "USD", "KWD"),
                                 ("50", "EUR", "JPY"), ("12.345", "KWD", "KWD")]:
            with self.subTest(pair=(src, dst)):
                self.assertEqual(fx_legacy.convert_amount(Decimal(amount), src, dst, t),
                                 legacy_expected(Decimal(amount), src, dst, t))
        self.assertIsInstance(fx_legacy.convert_amount(Decimal("1"), "USD", "EUR", t), float)

    def test_partner_report_unchanged(self):
        from tools.old_report import usd_totals
        lg = bank()
        expected = {a.id: legacy_expected(lg.balance(a.id), a.currency, "USD", lg.rates)
                    for a in lg.accounts.values()}
        self.assertEqual(usd_totals(lg), expected)

    def test_ledger_behaviour_kept(self):
        lg = bank()
        transfers = list(lg.transfers.values())
        self.assertEqual([t.fee for t in transfers],
                         [Decimal("6.17"), Decimal("1.67"), Decimal("3.89"), Decimal("0"), Decimal("0.50")])
        self.assertEqual(transfers[0].credited, money("1111.11", "EUR"))
        self.assertEqual(transfers[1].credited, money("50000", "JPY"))  # 49999.5 rounds half to even
        self.assertEqual(lg.balance("ann-usd"), Decimal("5000") - sum(t.amount.amount + t.fee for t in transfers))

    def test_conversion_and_reports_kept(self):
        from minibank.reports import account_summary, fees_by_currency
        lg = bank()
        self.assertEqual(convert(money("10.01", "USD"), "EUR", lg.rates, utc(2026, 2, 1)).amount, Decimal("9.0090"))
        summary = account_summary(lg)
        self.assertEqual(summary["cho-jpy"], f"{format_amount(lg.balance('cho-jpy'), 'JPY')} JPY")
        self.assertEqual(fees_by_currency(lg), {"USD": "12.23"})


if __name__ == "__main__":
    unittest.main()
