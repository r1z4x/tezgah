import time


class Client:
    def __init__(self, settings, opener):
        self.timeout = settings["timeout"]
        self.retry_limit = settings["retry_limit"]
        self.backoff = settings["backoff"]
        self.opener = opener

    def fetch(self, url):
        """One try, then up to retry_limit more, sleeping backoff * 2**n between."""
        for attempt in range(self.retry_limit + 1):
            try:
                return self.opener(url, self.timeout)
            except OSError:
                if attempt == self.retry_limit:
                    raise
                time.sleep(self.backoff * 2 ** attempt)
