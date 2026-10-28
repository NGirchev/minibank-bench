import unittest
from decimal import Decimal

from minibank.fx import RateTable
from minibank.ledger import Ledger
from minibank.money import money
from minibank.statement import monthly_statement
from minibank.timeutil import utc


class StatementTest(unittest.TestCase):
    def test_single_currency_month(self):
        lg = Ledger(RateTable())
        lg.open_account("a", "USD", "ann")
        lg.open_account("b", "USD", "ann")
        lg.deposit("a", money("50", "USD"), utc(2026, 1, 20))
        lg.deposit("a", money("100", "USD"), utc(2026, 2, 3))
        lg.transfer("a", "b", money("30", "USD"), utc(2026, 2, 10))
        st = monthly_statement(lg, "a", 2026, 2)
        self.assertEqual(st.opening, Decimal("50"))
        self.assertEqual(st.closing, Decimal("120"))
        self.assertEqual(len(st.lines), 2)

    def test_statement_snapshot(self):
        # Snapshot of the February statements as approved by the product team.
        t = RateTable()
        t.add("USD", "EUR", "0.90", utc(2026, 1, 1))
        t.add("USD", "EUR", "0.95", utc(2026, 3, 1))
        lg = Ledger(t)
        lg.open_account("us", "USD", "ann")
        lg.open_account("eu", "EUR", "bob")
        lg.deposit("us", money("500", "USD"), utc(2026, 2, 1))
        lg.transfer("us", "eu", money("100", "USD"), utc(2026, 2, 14))
        eu = monthly_statement(lg, "eu", 2026, 2)
        self.assertEqual([line.amount for line in eu.lines], [Decimal("95.0")])
        self.assertEqual(eu.closing, Decimal("95.0"))
        us = monthly_statement(lg, "us", 2026, 2)
        self.assertEqual([line.amount for line in us.lines], [Decimal("500"), Decimal("-100.50")])
        self.assertEqual(us.closing, Decimal("399.50"))


if __name__ == "__main__":
    unittest.main()
