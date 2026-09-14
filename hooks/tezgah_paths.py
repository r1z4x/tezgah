#!/usr/bin/env python3
"""Where tezgah is armed, what it is armed with, and which kill switches are on.

Shared by every host adapter - the Claude Code hooks, the Codex hooks, the
Cursor hooks, the opencode plugin and the status line - so there is exactly one
answer to "is this repo armed". Stdlib only, importable from any Python.

Roots, in order of precedence:
  1. TEZGAH_ROOTS  - os.pathsep-separated list (CI and one-offs)
  2. ~/.config/tezgah/config.json  {"roots": ["~/Projects", "~/work"]}
  3. ~/Projects    - the historical default, so an existing setup keeps working
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
BIN_DIR = os.path.join(CONFIG_DIR, "bin")
STATE_DIR = os.path.join(CONFIG_DIR, "state")
CACHE = os.path.join(HOME, ".cache", "tezgah")
DEFAULT_ROOT = os.path.join(HOME, "Projects")
# this file lives in <plugin>/hooks, so the plugin root is one level up and
# every path advertised to a model is derived from here rather than hardcoded
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CBM = "codebase-memory-mcp"
# canonical kill switches live in CONFIG_DIR; the pre-multi-host setup wrote
# them to ~/.claude, so that stays a recognized channel
OFF_DIRS = (CONFIG_DIR, os.path.join(HOME, ".claude"))


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


def off(name):
    """A kill switch, canonical (~/.config/tezgah) or legacy (~/.claude)."""
    return any(os.path.exists(os.path.join(d, name)) for d in OFF_DIRS)


def tool(name):
    """Stable installed path for a tezgah CLI, else the plugin's own copy, so
    the text injected into a session names something that actually exists."""
    for p in (os.path.join(BIN_DIR, name), os.path.join(PLUGIN_ROOT, "bin", name)):
        if os.path.exists(p):
            return p
    return os.path.join(BIN_DIR, name)
