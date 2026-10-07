import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import api  # noqa: E402


class GetFile(unittest.TestCase):
    def test_returns_the_callers_own_record(self):
        self.assertEqual(api.get_file({"user": "u1", "file_id": "f1"}),
                         {"id": "f1", "name": "a.txt", "uploaded_at": 100})

    def test_refuses_another_owners_record(self):
        self.assertEqual(api.get_file({"user": "u1", "file_id": "f4"}),
                         {"error": "not found"})

    def test_an_unknown_id_is_not_found(self):
        self.assertEqual(api.get_file({"user": "u1", "file_id": "nope"}),
                         {"error": "not found"})

    def test_every_route_names_a_handler(self):
        self.assertTrue(api.ROUTES)
        for name, handler in api.ROUTES.items():
            self.assertTrue(callable(handler), name)


if __name__ == "__main__":
    unittest.main()
