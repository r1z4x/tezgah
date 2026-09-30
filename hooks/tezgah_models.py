#!/usr/bin/env python3
"""The phase x tier x family model table, and the tier judgement the router asks for.

Which model runs which delegated task. The main thread keeps one model for the
whole session - a model switch re-reads the whole cached prefix at write price,
and the prompt cache is per model - so routing happens where it is free: at the
subagent a task is handed to. Every generated agent has a slot, every slot a model
per family, and each host gets the family it can run:

  Claude Code / Cursor  anthropic   frontmatter `model:` + `effort:`
  Codex                 openai      `model` + `model_reasoning_effort`
  opencode              any         a selector `refresh` found in `opencode models`
  omp                   anthropic when the session default is an Anthropic model,
                        any otherwise (or `tezgah-route --mode`); written to omp's
                        `task.agentModelOverrides`, frontier left to the default

The table is a dated snapshot: prices and ids are re-read from OpenRouter's public
model list by `tezgah-route --refresh` into CONFIG_DIR/models.json, which also
flags an id that left the list or a price that moved; scores are not re-read (they
need a key) and the snapshot says how old they are. Why these models, with the
measurements behind them: docs/models.md.

The tier judgement is deterministic first and a model second: a brief naming
stored data, a migration, credentials, the gate or security goes to frontier by
rule, because that is the one class the measured judge under-routed; otherwise
Jev answers one Choice over the tiers; with no key the caller's phase picks the
tier from the static table, and with no phase the middle tier is used.

Stdlib only; every network or subprocess failure is a fallback, never a raise.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import urllib.request

import tezgah_paths as tp

READ_ON = "2026-09-30"
STALE_DAYS = 60
OVERLAY = os.path.join(tp.CONFIG_DIR, "models.json")
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
MODES = ("auto", "anthropic", "any")
TIERS = ("cheap", "standard", "frontier")

# slot -> family -> (model, effort). Anthropic and OpenAI names are the hosts'
# own ids; `any` names are OpenRouter ids.
SLOTS = {
    "cheap": {"anthropic": ("claude-opus-5-5", "low"),
              "openai": ("gpt-6.1-sol", "low"),
              "any": ("z-ai/glm-5.3-flash", None)},
    "explore": {"anthropic": ("claude-opus-5-5", "medium"),
                "openai": ("gpt-6.1-sol", "low"),
                "any": ("deepseek/deepseek-v4.1-flash", None)},
    "standard": {"anthropic": ("claude-opus-5-5", "medium"),
                 "openai": ("gpt-6.1-sol", "high"),
                 "any": ("openai/gpt-6.1-sol", "high")},
    "frontier": {"anthropic": ("claude-opus-5-5", "high"),
                 "openai": ("gpt-6-astra", "high"),
                 "any": ("anthropic/claude-opus-5.5", "high")},
}
AGENT_SLOT = {"tezgah-cheap": "cheap", "tezgah-standard": "standard",
              "tezgah-frontier": "frontier", "tezgah-explorer": "explore",
              "tezgah-reviewer": "frontier", "tezgah-researcher": "frontier",
              "tezgah-verifier": "cheap"}
# The OpenRouter id of every model the table names, with its list price per 1M
# tokens (input, output) on READ_ON, so `refresh` can say what moved.
SNAPSHOT = {"anthropic/claude-opus-5.5": (4.0, 20.0),
            "openai/gpt-6.1-sol": (2.0, 10.0),
            "openai/gpt-6-astra": (10.0, 50.0),
            "z-ai/glm-5.3-flash": (0.15, 0.5),
            "deepseek/deepseek-v4.1-flash": (0.0198, 0.396)}

# ---------------------------------------------------------------- overlay ----


def overlay():
    try:
        with open(OVERLAY, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_overlay(data):
    try:
        os.makedirs(tp.CONFIG_DIR, exist_ok=True)
        tmp = OVERLAY + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, OVERLAY)
        return True
    except OSError:
        return False


# ------------------------------------------------------------ host models ----


def pick(agent, family):
    """(model, effort) for a generated agent on a family, or None: no slot."""
    slot = AGENT_SLOT.get(agent)
    return SLOTS[slot][family] if slot else None


def opencode_model(agent):
    """The selector `refresh` resolved for this agent's slot, or None (inherit)."""
    slot = AGENT_SLOT.get(agent)
    found = overlay().get("opencode") or {}
    return found.get(slot) if slot else None


def omp_mode(default_selector=None):
    """`anthropic` or `any`: the saved mode, else what the session default is."""
    mode = overlay().get("mode")
    if mode in ("anthropic", "any"):
        return mode
    return "anthropic" if str(default_selector or "").startswith("anthropic/") else "any"


def omp_overrides(mode):
    """{agent: omp selector} for `task.agentModelOverrides`. Frontier agents get
    no entry: they inherit the session default, the strongest model the user
    chose, in either mode."""
    out = {}
    for agent, slot in AGENT_SLOT.items():
        if slot == "frontier":
            continue
        family = "anthropic" if mode == "anthropic" else "any"
        model, effort = SLOTS[slot][family]
        selector = ("anthropic/" + model) if family == "anthropic" else ("openrouter/" + model)
        out[agent] = selector + (":" + effort if effort else "")
    return out


def _omp(*args):
    exe = shutil.which("omp")
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, "config"] + list(args), capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc if proc.returncode == 0 else None


def omp_get(key):
    proc = _omp("get", key, "--json")
    try:
        value = json.loads(proc.stdout).get("value") if proc else None
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, dict) else None


def apply_omp(remove=False):
    """Write (or, with `remove`, drop) the tezgah-* entries of omp's
    `task.agentModelOverrides`, keeping every entry the user has. Returns a
    one-line status, or None when omp is not answering."""
    current = omp_get("task.agentModelOverrides")
    if current is None:
        return None
    kept = {k: v for k, v in current.items() if not k.startswith("tezgah-")}
    mode = None
    if not remove:
        mode = omp_mode((omp_get("modelRoles") or {}).get("default"))
        kept.update(omp_overrides(mode))
    if kept == current:
        return "omp model overrides current (%s)" % (mode or "none")
    done = (_omp("set", "task.agentModelOverrides", json.dumps(kept)) if kept
            else _omp("reset", "task.agentModelOverrides"))
    if done is None:
        return "omp model overrides NOT written"
    return ("omp model overrides removed" if remove
            else "omp model overrides written (%s)" % mode)


# ---------------------------------------------------------------- refresh ----


def refresh(timeout=20):
    """Re-read prices and ids from OpenRouter, resolve opencode selectors, and
    write the overlay. Returns (lines, ok)."""
    data = overlay()
    lines = []
    try:
        with urllib.request.urlopen(OPENROUTER_MODELS, timeout=timeout) as resp:
            listed = {m["id"]: m for m in json.load(resp).get("data", [])}
    except Exception as exc:  # ponytail: any fetch failure keeps the old overlay
        return ["could not read %s (%s); nothing changed" % (OPENROUTER_MODELS, exc)], False
    ids = sorted(set(SNAPSHOT))
    prices, flags = {}, []
    for mid in ids:
        m = listed.get(mid)
        if not m:
            flags.append("%s is no longer in the OpenRouter list" % mid)
            continue
        p = m.get("pricing") or {}
        now = (round(float(p.get("prompt", 0)) * 1e6, 4),
               round(float(p.get("completion", 0)) * 1e6, 4))
        prices[mid] = now
        if tuple(now) != SNAPSHOT[mid]:
            flags.append("%s price moved: %s -> %s per 1M in/out" % (mid, SNAPSHOT[mid], now))
    data.update(read_on=datetime.date.today().isoformat(), prices=prices, flags=flags)
    oc = resolve_opencode()
    if oc is not None:
        data["opencode"] = oc
        lines.append("opencode selectors: %s" % (", ".join(
            "%s=%s" % kv for kv in sorted(oc.items())) or "none found"))
    if not save_overlay(data):
        return lines + ["could not write %s" % OVERLAY], False
    lines.insert(0, "%d model(s) read, %d flag(s)" % (len(prices), len(flags)))
    return lines + flags, True


def resolve_opencode(timeout=30):
    """{slot: selector} from `opencode models`, matching each slot's `any` id by
    its model name under whatever provider this machine configured; None when
    opencode is absent."""
    exe = shutil.which("opencode")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "models"], capture_output=True, text=True,
                             timeout=timeout).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    found = {}
    for slot, fams in SLOTS.items():
        want = fams["any"][0]
        name = want.split("/", 1)[-1]
        exact = [s for s in out if s == want]
        near = [s for s in out if s.endswith("/" + name)]
        if exact or near:
            found[slot] = (exact or near)[0]
    return found


def check(today=None):
    """(lines, stale): the table's age and the flags the last refresh left."""
    data = overlay()
    today = today or datetime.date.today()
    read = data.get("read_on") or READ_ON
    age = (today - datetime.date.fromisoformat(READ_ON)).days
    lines = ["scores and picks read %s (%d days ago); prices read %s" % (READ_ON, age, read),
             "omp mode: %s" % (data.get("mode") or "auto")]
    flags = data.get("flags") or []
    lines += ["flag: %s" % f for f in flags]
    stale = age > STALE_DAYS or bool(flags)
    if age > STALE_DAYS:
        lines.append("stale: re-read the phase scores (docs/models.md) and update the table")
    return lines, stale


# ------------------------------------------------------------------ route ----

OVERRIDE = re.compile(
    r"stored data|on disk|migrat\w*|credential\w*|secret\w*|password\w*|"
    r"tezgah_gate|tezgah_integrity|security|threat model|"
    r"\bauth(?:entication|orization)?\b", re.I)
JEV_TIER = {"mechanical": "cheap", "standard": "standard", "frontier": "frontier"}
PHASE_TIER = {"explore": "standard", "code": "standard", "mechanical": "cheap",
              "plan": "frontier", "review": "frontier", "research": "frontier"}
TIER_QUESTION = {
    "type": "choice",
    "instructions": (
        "A coding-agent orchestrator must pick the cheapest model tier that can do "
        "`task` correctly on the first attempt. Under-routing (a tier too weak) "
        "costs a rework loop; over-routing only costs money. Which tier does the "
        "task need?"),
    "criteria": {
        "mechanical": "files and change fully specified, no judgement: rename, "
                      "fixture, boilerplate, formatting, commit message, version "
                      "bump, a listed mechanical migration or translation",
        "standard": "bounded feature or bug fix in known code with a clear cause, "
                    "writing tests, code search and summarising, routine review of "
                    "a small diff, release notes",
        "frontier": "design or architecture choice, security-sensitive code, a "
                    "stored-data or ordering invariant, debugging with an unknown "
                    "cause, adversarial review of a large diff, research synthesis, "
                    "a hard-to-reverse decision",
    },
}


def route(brief, phase=None, ask=None):
    """{"agent", "tier", "why", "judged"} for one delegation brief.

    `ask` is the judge call (tezgah_judge.ask) - injected so the rule order is
    testable without the network; None means no judge is available."""
    hit = OVERRIDE.search(brief or "")
    if hit:
        return _pick("frontier", "override: %r" % hit.group(0))
    result = ask({"task": brief}, {"tier": TIER_QUESTION}) if ask else None
    answer = ((result or {}).get("answers") or {}).get("tier") or {}
    choice = answer.get("choice")
    if choice in JEV_TIER:
        probs = answer.get("probabilities") or {}
        out = _pick(JEV_TIER[choice], "jev %s %.2f" % (choice, float(probs.get(choice, 0))))
        out["judged"] = result
        return out
    if phase in PHASE_TIER:
        return _pick(PHASE_TIER[phase], "no judgement; static table for phase %s" % phase)
    return _pick("standard", "no judgement and no phase; the middle tier")


def _pick(tier, why):
    return {"agent": "tezgah-" + tier, "tier": tier, "why": why, "judged": None}
