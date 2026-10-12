import tempfile
import unittest
from pathlib import Path

from profiles.errors import ProfileError
from profiles.export import to_csv
from profiles.store import load


class StoreTest(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(ProfileError):
            load("/nonexistent/profile.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ProfileError):
                load(path)


class ExportTest(unittest.TestCase):
    def test_header_only_for_no_profiles(self):
        self.assertEqual(to_csv([]), "name,email,tags\n")


if __name__ == "__main__":
    unittest.main()
