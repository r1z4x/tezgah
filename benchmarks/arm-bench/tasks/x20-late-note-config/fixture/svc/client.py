"""A client that retries on connection failures."""


class Client:
    """Sends requests through `transport`, a callable that takes a request and
    returns a response or raises ConnectionError.

    A request is tried once and then retried up to `retries` more times while
    the transport raises ConnectionError; if every attempt fails, the last
    ConnectionError is raised."""

    def __init__(self, transport, retries):
        self.transport = transport
        self.retries = retries

    @classmethod
    def from_config(cls, config, transport):
        return cls(transport, config.retries)

    def send(self, request):
        last = None
        for _ in range(self.retries):
            try:
                return self.transport(request)
            except ConnectionError as exc:
                last = exc
        raise last
