import unittest

from src.pricing import cart_total_cents, member_discount_cents


class MemberDiscountTests(unittest.TestCase):
    def test_nine_percent_of_a_round_cart(self):
        self.assertEqual(member_discount_cents(1000), 90)
        self.assertEqual(member_discount_cents(2000), 180)
        self.assertEqual(member_discount_cents(300), 27)

    def test_empty_cart_has_no_discount(self):
        self.assertEqual(member_discount_cents(0), 0)


class CartTotalTests(unittest.TestCase):
    def test_plain_cart_pays_the_subtotal_and_the_tax(self):
        self.assertEqual(cart_total_cents(1000), 1070)

    def test_member_cart_pays_the_subtotal_less_the_discount_and_the_tax(self):
        self.assertEqual(cart_total_cents(1000, member=True), 980)


if __name__ == "__main__":
    unittest.main()
