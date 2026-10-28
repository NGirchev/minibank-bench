import unittest
from decimal import Decimal

from minibank.money import Money, format_amount, money, quantize


class MoneyTest(unittest.TestCase):
    def test_rounding_half_even(self):
        self.assertEqual(quantize(Decimal("2.345"), "USD"), Decimal("2.34"))
        self.assertEqual(quantize(Decimal("2.355"), "USD"), Decimal("2.36"))
        self.assertEqual(quantize(Decimal("1500.5"), "JPY"), Decimal("1500"))

    def test_format(self):
        self.assertEqual(format_amount(Decimal("1500"), "JPY"), "1500")
        self.assertEqual(format_amount(Decimal("12.3454"), "KWD"), "12.345")
        self.assertEqual(format_amount(Decimal("-3.1"), "USD"), "-3.10")

    def test_arithmetic_and_validation(self):
        self.assertEqual(money("1.10", "EUR") + money("2", "EUR"), money("3.10", "EUR"))
        with self.assertRaises(ValueError):
            money("1", "EUR") + money("1", "USD")
        with self.assertRaises(TypeError):
            money(1.5, "EUR")
        with self.assertRaises(ValueError):
            Money(Decimal(1), "XXX")


if __name__ == "__main__":
    unittest.main()
