"""Service settings, read from the [service] section of an INI file.

Keys: host (required), port (default 8080), timeout in seconds (default 5.0),
retries (default 3). An environment variable SVC_<KEY> (SVC_HOST, SVC_PORT, ...)
overrides the file. Every value is parsed and range-checked; anything the
service cannot run with raises ConfigError.
"""
import configparser
import os
from dataclasses import dataclass

from svc.errors import ConfigError


@dataclass(frozen=True)
class Config:
    host: str
    port: int = 8080
    timeout: float = 5.0
    retries: int = 3


TYPES = {"host": str, "port": int, "timeout": float, "retries": int}
VALID = {
    "host": lambda v: bool(v),
    "port": lambda v: 1 <= v <= 65535,
    "timeout": lambda v: v > 0,
    "retries": lambda v: v >= 0,        # 0 = try once, never retry
}


def parse(key, text):
    try:
        value = TYPES[key](text.strip())
    except ValueError:
        raise ConfigError("%s: not a valid %s: %r" % (key, TYPES[key].__name__, text)) from None
    if not VALID[key](value):
        raise ConfigError("%s out of range: %r" % (key, text))
    return value


def load(path):
    """The Config stored in the INI file at `path`, with SVC_* overrides."""
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise ConfigError("cannot read %s" % (path,))
    if not parser.has_section("service"):
        raise ConfigError("%s has no [service] section" % (path,))
    raw = dict(parser["service"])
    for key in TYPES:
        override = os.environ.get("SVC_" + key.upper())
        if override is not None:
            raw[key] = override
    if "host" not in raw:
        raise ConfigError("missing host")
    values = {key: parse(key, raw[key]) for key in TYPES if key in raw}
    return Config(**values)
