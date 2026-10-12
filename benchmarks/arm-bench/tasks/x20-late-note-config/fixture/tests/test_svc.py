import unittest

from svc.client import Client
from svc.config import Config, load


class ConfigTest(unittest.TestCase):
    def test_reads_host(self):
        self.assertEqual(load("service.ini").host, "api.internal")

    def test_defaults(self):
        self.assertEqual(Config(host="h"), Config("h", 8080, 5.0, 3))


class ClientTest(unittest.TestCase):
    def test_first_attempt_succeeds(self):
        client = Client(lambda request: "ok:" + request, retries=3)
        self.assertEqual(client.send("ping"), "ok:ping")


if __name__ == "__main__":
    unittest.main()
