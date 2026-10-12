import configparser
import os
from pathlib import Path

DEFAULTS_FILE = Path(__file__).resolve().parent.parent / "config" / "defaults.ini"
ENV_PREFIX = "FETCHER_"
TYPES = {"timeout": int, "max_retries": int, "backoff": float}


def load(path=None, env=None, overrides=None):
    """Settings from defaults.ini, then `path`, then `env`, then `overrides`.

    In the INI file a key is the setting name with dashes; in the environment
    it is ENV_PREFIX plus the name in upper case (README.md)."""
    env = os.environ if env is None else env
    parser = configparser.ConfigParser()
    parser.read(DEFAULTS_FILE)
    if path:
        parser.read(path)
    section = parser["fetcher"]
    out = {}
    for name, kind in TYPES.items():
        raw = section.get(name.replace("_", "-"))
        raw = env.get(ENV_PREFIX + name.upper(), raw)
        out[name] = kind(raw)
    for name, value in (overrides or {}).items():
        if value is not None:
            out[name] = TYPES[name](value)
    return out
