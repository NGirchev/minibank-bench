import unittest
from decimal import Decimal

from minibank.fx import RateTable, convert
from minibank.money import money
from minibank.timeutil import utc


def table():
    t = RateTable()
    t.add("USD", "EUR", "0.90", utc(2026, 1, 1))
    t.add("USD", "EUR", "0.95", utc(2026, 3, 1))
    t.add("USD", "JPY", "150", utc(2026, 1, 1))
    return t


class FxTest(unittest.TestCase):
    def test_effective_rate(self):
        t = table()
        self.assertEqual(t.rate("USD", "EUR", utc(2026, 2, 28, 23, 59)), Decimal("0.90"))
        self.assertEqual(t.rate("USD", "EUR", utc(2026, 3, 1)), Decimal("0.95"))
        with self.assertRaises(LookupError):
            t.rate("USD", "EUR", utc(2025, 12, 31))

    def test_inverse_and_cross(self):
        t = table()
        self.assertEqual(t.rate("JPY", "USD", utc(2026, 2, 1)), Decimal(1) / Decimal(150))
        self.assertEqual(t.rate("EUR", "JPY", utc(2026, 2, 1)), (Decimal(1) / Decimal("0.90")) * Decimal(150))

    def test_convert_not_rounded(self):
        t = table()
        self.assertEqual(convert(money("10.01", "USD"), "EUR", t, utc(2026, 2, 1)).amount, Decimal("9.0090"))

    def test_correct(self):
        t = table()
        t.correct("USD", "EUR", utc(2026, 3, 1), "0.96")
        self.assertEqual(t.rate("USD", "EUR", utc(2026, 3, 2)), Decimal("0.96"))


if __name__ == "__main__":
    unittest.main()
