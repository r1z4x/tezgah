import time


class Client:
    def __init__(self, settings, opener):
        self.timeout = settings["timeout"]
        self.max_retries = settings["max_retries"]
        self.backoff = settings["backoff"]
        self.opener = opener

    def fetch(self, url):
        """One try, then up to max_retries more, sleeping backoff * 2**n between."""
        for attempt in range(self.max_retries + 1):
            try:
                return self.opener(url, self.timeout)
            except OSError:
                if attempt == self.max_retries:
                    raise
                time.sleep(self.backoff * 2 ** attempt)
