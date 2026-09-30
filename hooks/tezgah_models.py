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
                        `task.agentModelOverrides`, and to its `modelRoles.plan`
                        and `.slow`, on the frontier row

Two accessors are the table's public face, so a caller that needs a cheap or a
strong model names none of its own: `frontier_model(family)` and
`cheap_model(family)` return that row's `(model, effort)`, or None when the
family has no such row.

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

import tezgah_integrity as ti
import tezgah_judge as tj
import tezgah_paths as tp

READ_ON = "2026-09-30"
STALE_DAYS = 60
OVERLAY = os.path.join(tp.CONFIG_DIR, "models.json")
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
MODES = ("auto", "anthropic", "any", "off")
# The two status markers `bin/tezgah-setup` classifies an `apply_omp()` line by:
# a skip is not a write and not a failure - the user's omp is left untouched, and
# nothing is left to repair, which is why the status report excuses it rather
# than showing it as a missing row.
SKIP_MARK = "skipped:"
FAIL_MARK = "NOT written"
# omp's own agent dir: the same one `omp_config` in bin/tezgah-setup pins with
# PI_CODING_AGENT_DIR, so a write lands beside the hook the installer registered.
OMP_AGENT = os.path.join(tp.HOME, ".omp", "agent")
# The agents omp bundles (omp://task-agent-discovery.md:129-130). They resolve
# through `task.agentModelOverrides` before their own model
# (omp://task-agent-discovery.md:217), which is the only way to route them, so
# `scout`/`sonic`/`task` ride the slots this table writes. omp's own `reviewer`
# and `security-reviewer` are not tezgah's to route: the generated
# `tezgah-reviewer` is the one that carries the frontier row.
BUNDLED = {"scout": "explore", "sonic": "cheap", "task": "standard"}
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
    # The frontier row names a concrete model on every family: the strongest
    # Anthropic run the snapshot prices (Opus 5.5 @high, 56.6 Terminal-Bench 4.0
    # at $1.82/task on AA v4.3), OpenAI's own frontier id, and the same Opus 5.5
    # through OpenRouter at $4/$20 per 1M (docs/models.md, read 2026-09-30).
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


# The overlay's known fields and the type each has to be: a field of another
# type reads as absent, so a hand-edited or half-written file cannot make a
# caller raise (agent generation reads `opencode` on every session start) or
# make `--check` print one flag per character.
OVERLAY_TYPES = {"mode": str, "read_on": str, "prices": dict, "opencode": dict,
                 "omp_written": dict, "flags": list}


def overlay():
    try:
        with open(OVERLAY, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items()
            if k not in OVERLAY_TYPES or isinstance(v, OVERLAY_TYPES[k])}


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


def frontier_model(family):
    """(model, effort) the frontier row names on `family`, or None: no such row.

    What the design surface and omp's plan role run on, so neither has to name a
    model of its own (docs/models.md)."""
    return SLOTS["frontier"].get(family)


def cheap_model(family):
    """(model, effort) the cheap row names on `family`, or None: no such row.

    The one place the cheap tier is named: `bin/codegen`'s default and the
    judge's fallback read this, so a refresh moves every cheap path."""
    return SLOTS["cheap"].get(family)


def opencode_model(agent):
    """The selector `refresh` resolved for this agent's slot, or None (inherit)."""
    slot = AGENT_SLOT.get(agent)
    found = overlay().get("opencode") or {}
    return found.get(slot) if slot else None


def openrouter_ready():
    """Whether an OpenRouter credential resolves, the channels `consult` and the
    judge's fallback use (`tp.PROVIDER_KEYS`)."""
    env, home = tp.PROVIDER_KEYS["openrouter"]
    if os.environ.get(env, "").strip():
        return True
    try:
        with open(os.path.join(tp.HOME, home), encoding="utf-8") as fh:
            return bool(fh.read().strip())
    except OSError:
        return False


def omp_mode(default_selector=None):
    """`anthropic` or `any`: the saved mode, else the default's own family.

    A non-Anthropic default reads as `any`, never as a silent fall back to the
    Anthropic column - the caller decides what to do when the OpenRouter
    credential the `any` selectors need is missing (`apply_omp` writes nothing
    and says so)."""
    mode = overlay().get("mode")
    if mode in ("anthropic", "any", "off"):
        return mode
    return "anthropic" if str(default_selector or "").startswith("anthropic/") else "any"


# The omp roles this table writes, as flat `modelRoles.<role>` keys: `plan` is
# the model plan mode designs on - the one surface where a session spends its own
# tokens on design - and `slow` is omp's hard-question role (omp://models.md:483,
# omp://settings.md:116-118). Both carry the frontier row.
OMP_ROLES = ("plan", "slow")


def _selector(family, slot):
    """`<provider>/<model>[:<effort>]` for one slot on one family, the shape omp
    takes for a model override and for a role alike (omp://models.md:492-505):
    the Anthropic column names the host's own id, `any` an OpenRouter id."""
    model, effort = SLOTS[slot][family]
    selector = ("anthropic/" + model if family == "anthropic"
                else "openrouter/" + model)
    return selector + (":" + effort if effort else "")


def omp_overrides(mode):
    """{agent: omp selector} for `task.agentModelOverrides`, tezgah roles and the
    bundled agents alike, or {} when the mode cannot run on this machine.

    Every slot is written, frontier included: a frontier agent the record left
    out would run on whatever model the session started with, and in the `any`
    mode that is measured as a flash model, so security-sensitive work would run
    below the row. Only `tezgah-orchestrator` stays outside the record - it is
    the main thread's own agent."""
    if mode == "any" and not openrouter_ready():
        return {}  # nothing can run here; `apply_omp` says so and writes nothing
    family = "anthropic" if mode == "anthropic" else "any"
    return {agent: _selector(family, slot)
            for agent, slot in dict(AGENT_SLOT, **BUNDLED).items()}


def omp_role_overrides(mode):
    """{"modelRoles.<role>": selector} for `OMP_ROLES`, or {} when the mode
    cannot run here.

    Plan mode is the one surface where a session designs on its own tokens, so
    it is pinned to the frontier row of the mode's family rather than left on
    whatever model the session happened to start with; `slow` follows it. The
    same OpenRouter gate as `omp_overrides` applies, and `off` resolves to {} -
    it writes nothing."""
    if mode not in ("anthropic", "any"):
        return {}
    if mode == "any" and not openrouter_ready():
        return {}
    family = "anthropic" if mode == "anthropic" else "any"
    return {"modelRoles." + role: _selector(family, "frontier")
            for role in OMP_ROLES}


def _omp(*args):
    """Run `omp config <args>` the way the installer does.

    `tp.omp_bin()` is the installer's own lookup (TEZGAH_OMP_BIN, then PATH,
    then a per-user bin dir) and PI_CODING_AGENT_DIR pins the CLI to the agent
    dir tezgah writes into, so the value is read and written in one profile.

    `cwd` is HOME on purpose: `config get` answers the EFFECTIVE value, with the
    project layer of the working directory merged in, while `config set` writes
    the global file - so from a repository that carries a `.omp/config.yml`, a
    project entry would be copied machine-wide and the mode would be chosen from
    a project default (omp://settings.md:64-65)."""
    exe = tp.omp_bin()
    if not exe:
        return None
    env = dict(os.environ, PI_CODING_AGENT_DIR=OMP_AGENT)
    try:
        proc = subprocess.run([exe, "config"] + list(args), capture_output=True,
                              text=True, timeout=30, env=env, cwd=tp.HOME)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc if proc.returncode == 0 else None


def _omp_set(key, value):
    return (_omp("set", key, json.dumps(value)) if value
            else _omp("reset", key))


def omp_get(key):
    proc = _omp("get", key, "--json")
    try:
        value = json.loads(proc.stdout).get("value") if proc else None
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, dict) else None


def _ours_by_shape(key, value):
    """True when `value` is exactly a selector this table generates for `key`.

    The adoption rule for a machine tezgah wrote to before it recorded
    `omp_written`: only one of our own selectors is ever taken over, so a value
    the user picked by hand is never claimed - unless it is a byte-identical copy
    of the selector this table generates for that key in some mode, which is
    indistinguishable from our own write and is treated as ours. A role key is
    adopted the same way, from `omp_role_overrides`."""
    if not isinstance(value, str):
        return False
    return any(omp_overrides(mode).get(key) == value or
               omp_role_overrides(mode).get(key) == value
               for mode in ("anthropic", "any"))


def _reconcile(current, written, want):
    """(new, owns) for one flat {key: value} record, keys tezgah's own and the
    user's alike: `current` what omp holds, `written` the last recorded write,
    `want` what this mode asks for.

    An entry is tezgah's to change only while it is absent or still carries what
    `omp_written` recorded (or, on a machine written before that record existed,
    one of the table's own selectors - `_ours_by_shape`). A value the user
    changed by hand is left alone, an entry tezgah never wrote is never dropped,
    and ours that is no longer wanted goes."""
    new, owns = {}, {}
    for key in sorted(set(current) | set(written) | set(want)):
        cur = current.get(key)
        mine = (key in written and cur == written[key]) or (
            key not in written and _ours_by_shape(key, cur))
        if key in want:
            if cur is None or mine:
                new[key], owns[key] = want[key], want[key]
            else:
                new[key] = cur  # the user's own choice for this key wins
        elif mine:
            # ours, and no longer wanted: drop it. `cur != written.get(key)` is
            # only a user change when tezgah actually recorded a value - an
            # adopted entry has no record, so comparing against None would keep
            # every pre-record install's overrides forever.
            if key in written and cur is not None and cur != written[key]:
                new[key] = cur  # the user changed ours: keep it
        elif cur is not None:
            new[key] = cur
    return new, owns


def apply_omp(remove=False):
    """Write (or, with `remove`, drop) this table's entries of omp's
    `task.agentModelOverrides` and its `modelRoles.plan` and `.slow`, leaving
    everything else as it is.

    Ownership, because `config set` replaces the whole record: an entry is
    tezgah's to change only while it is absent or still carries what the last
    write recorded in `omp_written` (or, on a machine written before that
    record existed, one of the table's own selectors - `_ours_by_shape`); roles
    are recorded under their flat `modelRoles.<role>` key in the same record. A
    value the user changed by hand is left alone, and an entry tezgah never
    wrote is never dropped. omp's bundled agents are covered too (see BUNDLED),
    and the roles are the same rule applied to `modelRoles`.

    `any` needs a resolvable OpenRouter credential: without one the overrides
    could not run, so nothing is written and the status says so. Returns a
    one-line status, or None when omp is not answering."""
    current = omp_get("task.agentModelOverrides")
    roles = omp_get("modelRoles")
    if current is None or roles is None:
        return None
    written = overlay().get("omp_written") or {}
    mode, want, want_roles = None, {}, {}
    if not remove:
        mode = omp_mode(roles.get("default"))
        if mode == "off":
            # the user asked for no routing: drop every entry this table wrote
            # and write nothing. A provider the selectors need can run out of
            # budget (measured: an OpenRouter key that could not afford the
            # request), and the way back must not have to be `--uninstall`.
            remove = True
        elif mode == "any" and not openrouter_ready():
            return ("omp model overrides %s the any mode needs an OpenRouter key "
                    "(or `tezgah-route --mode anthropic`)" % SKIP_MARK)
        else:
            want = omp_overrides(mode)
            want_roles = omp_role_overrides(mode)
    flat_roles = {"modelRoles." + role: roles.get(role) for role in OMP_ROLES}
    new, owns = _reconcile(current, written, want)
    new_roles, owns_roles = _reconcile(flat_roles, written, want_roles)
    owns.update(owns_roles)
    merged = dict(roles)  # every other role the user set stays as it is
    for key in flat_roles:  # a role this table drops leaves no key behind
        role = key.split(".", 1)[1]
        value = new_roles.get(key)
        if value is None:
            merged.pop(role, None)
        else:
            merged[role] = value
    if owns == written and new == current and merged == roles:
        return "omp model overrides current (%s)" % (mode or "none")
    # the write comes first: recording what tezgah owns before the record it
    # describes exists would leave a failed write claiming entries it never wrote
    if new != current and _omp_set("task.agentModelOverrides", new) is None:
        return "omp model overrides NOT written"
    if merged != roles and _omp_set("modelRoles", merged) is None:
        return "omp model overrides NOT written"
    data = overlay()
    data["omp_written"] = owns
    if not save_overlay(data):
        return ("omp model overrides written, ownership NOT recorded "
                "(overlay unreadable)")
    return ("omp model overrides removed (%s)" % (mode or "uninstall") if remove
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

# The classes that go to frontier by rule, before any judgement: the data and
# secret shapes a wrong call cannot be undone on, and the gate's own files.
# Word-bounded on purpose - `migrate_rows` is a rename, `secretary` is not a
# secret, `password-less` is a property - while `\bsecurity\b` is kept even
# when it names a file, because an over-route costs money and an under-route
# costs a rework loop.
OVERRIDE = re.compile(
    r"stored data|on disk|\bpersist\w*|\bschemas?\b|"
    r"\bmigrat(?:e|es|ed|ing|ion|ions|or)\b|"
    r"\bcredential\w*|\bsecrets?\b|\bpasswords?\b(?!-less)|"
    r"\bapi[- ]keys?\b|\baccess token\b|\brefresh token\b|\bsession token\b|"
    r"\bsession cookies?\b|\bsigning keys?\b|\bjwt\b|\boauth\b|\bauthn\b|"
    r"\bauthz?\b|tezgah_gate|tezgah_integrity|\bsecurity\b|threat model|"
    r"\bencrypt\w*|\bauthentication\b|\bauthorization\b|\bpii\b|"
    r"customer records", re.I)
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
    testable without the network; None means no judge is available. The brief
    goes out redacted (`ti.redact`, the reader the ledger uses) and only when no
    override matched: a brief naming a credential never leaves the machine.
    Answers are read through the seam's own accessors, so a malformed reply is
    the same as no reply and this never raises."""
    hit = OVERRIDE.search(brief or "")
    if hit:
        return _pick("frontier", "override: %r" % hit.group(0))
    result = ask({"task": ti.redact(brief or "")}, {"tier": TIER_QUESTION}) if ask else None
    choice = tj.choice(result, "tier")
    if choice in JEV_TIER:
        chance = tj.noul(result, "tier", choice)
        out = _pick(JEV_TIER[choice], "jev %s%s" % (
            choice, "" if chance is None else " %.2f" % chance))
        out["judged"] = result
        return out
    if phase in PHASE_TIER:
        return _pick(PHASE_TIER[phase], "no judgement; static table for phase %s" % phase)
    return _pick("standard", "no judgement and no phase; the middle tier")


def _pick(tier, why):
    return {"agent": "tezgah-" + tier, "tier": tier, "why": why, "judged": None}
