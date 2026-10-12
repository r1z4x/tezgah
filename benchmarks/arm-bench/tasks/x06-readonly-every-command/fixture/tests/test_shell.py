import json
import tempfile
import unittest
from pathlib import Path

from notes.commands import Shell
from notes.errors import ReadOnlyError
from notes.store import Store


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "notes.json"
        self.path.write_text(json.dumps({"milk": "buy milk", "call": "call mum"}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_then_show(self):
        shell = Shell(Store(self.path))
        shell.run("add eggs buy eggs")
        self.assertEqual(Shell(Store(self.path)).run("show eggs"), "buy eggs")

    def test_rename(self):
        shell = Shell(Store(self.path))
        shell.run("rename milk dairy")
        self.assertEqual(shell.run("list"), ["call", "dairy"])

    def test_tag(self):
        shell = Shell(Store(self.path))
        self.assertEqual(shell.run("tag milk shop"), "buy milk #shop")

    def test_read_only_store_rejects_add(self):
        before = self.path.read_bytes()
        store = Store(self.path, readonly=True)
        with self.assertRaises(ReadOnlyError):
            Shell(store).run("add eggs buy eggs")
        self.assertNotIn("eggs", store.items)
        self.assertEqual(self.path.read_bytes(), before)

    def test_read_only_store_still_lists(self):
        store = Store(self.path, readonly=True)
        self.assertEqual(Shell(store).run("list"), ["call", "milk"])


if __name__ == "__main__":
    unittest.main()
