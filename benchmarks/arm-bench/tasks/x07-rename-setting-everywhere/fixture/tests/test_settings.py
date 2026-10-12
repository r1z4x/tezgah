import unittest

from fetcher import settings
from fetcher.client import Client


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        loaded = settings.load(env={})
        self.assertEqual(loaded["timeout"], 10)
        self.assertEqual(loaded["retry_limit"], 3)
        self.assertEqual(loaded["backoff"], 0.5)

    def test_environment_wins_over_defaults(self):
        self.assertEqual(settings.load(env={"FETCHER_TIMEOUT": "4"})["timeout"], 4)

    def test_client_retries_retry_limit_times(self):
        calls = []

        def opener(url, timeout):
            calls.append(url)
            raise OSError("down")

        client = Client({"timeout": 1, "retry_limit": 2, "backoff": 0}, opener)
        with self.assertRaises(OSError):
            client.fetch("http://example.invalid")
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
