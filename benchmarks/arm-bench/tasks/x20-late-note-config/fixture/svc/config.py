"""Service settings, read from the [service] section of an INI file.

Keys: host (required), port (default 8080), timeout in seconds (default 5.0),
retries (default 3).
"""
import configparser
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    host: str
    port: int = 8080
    timeout: float = 5.0
    retries: int = 3


def load(path):
    """The Config stored in the INI file at `path`."""
    parser = configparser.ConfigParser()
    parser.read(path)
    section = parser["service"]
    return Config(host=section["host"],
                  port=section.get("port", 8080),
                  timeout=section.get("timeout", 5.0),
                  retries=section.get("retries", 3))
