SHOWN = ("timeout", "max_retries", "backoff")


def summary(client):
    """One line naming each shown setting as the client holds it."""
    return " ".join("%s=%s" % (name, getattr(client, name)) for name in SHOWN)
