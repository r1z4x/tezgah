#!/usr/bin/env python3
"""Where tezgah is armed, and what it needs to be armed with.

The roots are read from, in order of precedence:
  1. TEZGAH_ROOTS  — os.pathsep-separated list (handy for CI and one-offs)
  2. ~/.config/tezgah/config.json  {"roots": ["~/Projects", "~/work"]}
  3. ~/Projects    — the historical default, so an existing setup keeps working
Hooks are spawned by the app, not by an interactive shell, so the config file
is the reliable channel; the env var is the escape hatch, not the contract.
"""
import json
import os
import shutil

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "tezgah")
CONFIG = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_ROOT = os.path.join(HOME, "Projects")
CBM = "codebase-memory-mcp"


def config():
    try:
        with open(CONFIG) as fh:
            return json.load(fh)
    except Exception:  # missing, unreadable or malformed: fall back to defaults
        return {}


def roots():
    """Configured roots as absolute real paths, longest (most specific) first."""
    env = os.environ.get("TEZGAH_ROOTS")
    raw = env.split(os.pathsep) if env else (config().get("roots") or [DEFAULT_ROOT])
    out = set()
    for p in raw:
        p = os.path.expanduser((p or "").strip())
        if not p:
            continue
        try:
            out.add(os.path.realpath(p))
        except OSError:
            pass
    return sorted(out, key=len, reverse=True)


def root_for(path):
    """The configured root containing path, or None when tezgah is not armed here."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return None
    for r in roots():
        if real == r or real.startswith(r + os.sep):
            return r
    return None


def cbm_bin():
    """The codebase-memory-mcp executable, or None when it is not installed."""
    return shutil.which(os.environ.get("TEZGAH_CBM_BIN") or config().get("cbm_bin") or CBM)


def have_consult_key():
    return bool(os.environ.get("OPENROUTER_API_KEY")) or os.path.exists(
        os.path.join(HOME, ".config", "openrouter", "key"))
