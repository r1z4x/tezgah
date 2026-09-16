import unittest

from inventory.cart import add_item, make_cart


class T7MutableDefault(unittest.TestCase):
    def test_carts_are_independent(self):
        first = make_cart()
        add_item(first, "x", 1.0)
        second = make_cart()
        self.assertEqual(second["items"], [])

    def test_seeded_cart_is_returned(self):
        seeded = [{"name": "y", "price": 2.0, "qty": 1}]
        cart = make_cart(seeded)
        self.assertEqual(cart["items"], seeded)
        self.assertEqual(make_cart()["items"], [])


if __name__ == "__main__":
    unittest.main()
