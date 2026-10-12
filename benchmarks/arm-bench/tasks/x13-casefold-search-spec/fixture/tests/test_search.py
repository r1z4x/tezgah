import unittest

from crm.search import search

CUSTOMERS = [
    {"id": 1, "name": "Gärtnerei Straße"},
    {"id": 2, "name": "Anna Keller"},
    {"id": 3, "name": "Bruno Keller"},
]


def ids(found):
    return [c["id"] for c in found]


class Search(unittest.TestCase):
    def test_ticket_88_strasse_finds_strasse(self):
        self.assertEqual(ids(search("STRASSE", CUSTOMERS)), [1])

    def test_a_plain_prefix(self):
        self.assertEqual(ids(search("anna", CUSTOMERS)), [2])


if __name__ == "__main__":
    unittest.main()
