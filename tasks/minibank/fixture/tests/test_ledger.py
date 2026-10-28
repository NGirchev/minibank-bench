import unittest
from decimal import Decimal

from minibank.fx import RateTable
from minibank.ledger import Ledger
from minibank.money import money
from minibank.timeutil import utc


def ledger():
    t = RateTable()
    t.add("USD", "EUR", "0.90", utc(2026, 1, 1))
    t.add("USD", "JPY", "150", utc(2026, 1, 1))
    lg = Ledger(t)
    lg.open_account("alice-usd", "USD", "alice")
    lg.open_account("alice-eur", "EUR", "alice")
    lg.open_account("bob-jpy", "JPY", "bob")
    lg.deposit("alice-usd", money("1000", "USD"), utc(2026, 1, 5))
    return lg


class LedgerTest(unittest.TestCase):
    def test_same_owner_transfer_is_free(self):
        lg = ledger()
        tr = lg.transfer("alice-usd", "alice-eur", money("100", "USD"), utc(2026, 1, 10))
        self.assertEqual(tr.fee, Decimal(0))
        self.assertEqual(lg.balance("alice-usd"), Decimal("900"))
        self.assertEqual(lg.balance("alice-eur"), Decimal("90.00"))

    def test_fee_and_conversion(self):
        lg = ledger()
        tr = lg.transfer("alice-usd", "bob-jpy", money("10.01", "USD"), utc(2026, 1, 10))
        self.assertEqual(tr.fee, Decimal("0.50"))
        self.assertEqual(lg.balance("alice-usd"), Decimal("989.49"))
        self.assertEqual(lg.balance("bob-jpy"), Decimal("1502"))

    def test_insufficient_funds(self):
        lg = ledger()
        with self.assertRaises(ValueError):
            lg.transfer("alice-usd", "bob-jpy", money("999.80", "USD"), utc(2026, 1, 10))

    def test_balance_at(self):
        lg = ledger()
        self.assertEqual(lg.balance("alice-usd", at=utc(2026, 1, 5)), Decimal(0))
        self.assertEqual(lg.balance("alice-usd", at=utc(2026, 1, 6)), Decimal(1000))


if __name__ == "__main__":
    unittest.main()
