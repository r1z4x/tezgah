#!/usr/bin/env python3
"""Derive the clause-ablation and forced-delegation arms from the installed agent dir.

    python3 make_variants.py                       # (re)deploy arms/orx-*/
    python3 make_variants.py omp+tezgah-delegate   # (re)deploy the named arms only
    ARMBENCH_SUBAGENT_MODEL=<model> python3 make_variants.py omp+tezgah-delegate

Each variant is the installed omp agent dir with exactly one clause removed from
its `RULES.md`, so an arm that loads it runs the same harness minus that clause:
the arm sets `PI_CODING_AGENT_DIR` to the directory, omp reads `RULES.md`,
`hooks/`, `agents/` and the rest of the contract from there, and `omp+tezgah`
reads the installed dir. The copied bridge is the installed byte and pins the
same checkout, so the one file that differs from `omp+tezgah` is the contract.

A variant is not a `RULES.md` on its own: an agent dir holding the contract and
no bridge loads no harness, so the row measures an inert host - `bench.py`'s
pre-flight refuses it before any spend, and `session_rows` would be 0 on every
row. Per-run state (sessions, SQLite DBs, caches) is dropped here because omp
recreates it on first run.

The positive control is `orx-no-reporting`: clause 1 is the reply-language rule,
and `c04-turkish-explain-readonly` grades it, so if that ablation does not break
c04 the variant mechanism itself is broken and no other reading is admissible.

The delegate arm (`omp+tezgah-delegate`, built only when named) adds one
paragraph to `RULES.md` instead of removing one: the orchestrator hands every
edit to the tezgah-* worker `tezgah-route` names, so the role text is read on a
bench where the plain arm never spawns a subagent (plan 090's spike). Its
`agents/` are rendered by this checkout's `hooks/tezgah_agents.py`, and every
subagent model override in `config.yml` is pinned to `SUBAGENT_MODEL` so a
worker runs on the bench model rather than the installed frontier chain.

Every input is validated before any arm directory is written, so a refused run
leaves no armed-looking wrong arm behind.
"""
import os
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path.home() / ".omp" / "agent"

# per-run state, not arm configuration: omp recreates every one of these
RUN_STATE = ("sessions", "blobs", "cache", "terminal-sessions", "custom-session-files",
             "agent.db*", "models.db*", "history.db*", "config.yml.lock")

# variant name -> the clause lead to strip
CLAUSES = {
    "orx-no-reporting": "**Turkish, BLUF.**",
    "orx-no-ponytail": "**Ponytail (minimal code).**",
    "orx-no-whole-ask": "**Deliver the whole ask; never the shortcut.**",
    "orx-no-integrity": '**Integrity: evidence, or a named blocker.**',
}

# the bench model every subagent runs on; a run on another model sets it
SUBAGENT_MODEL = os.environ.get("ARMBENCH_SUBAGENT_MODEL", "deepseek/deepseek-v4-flash")
MODEL_ID = r"[\w./:,-]+"
ROUTE = pathlib.Path.home() / ".config" / "tezgah" / "bin" / "tezgah-route"
DELEGATE_ARMS = ("omp+tezgah-delegate",)
DELEGATE = (
    "**Delegate every edit (bench arm).** You are the orchestrator in this session\n"
    "and you never change a file yourself: no `edit`, no `write`, no shell command\n"
    "that writes a file. For each code change, first run\n"
    "`%s \"<one-line brief>\"` in the shell, then spawn exactly\n"
    "the agent named on its `agent:` line with the `task` tool: set the task's\n"
    "`agent` field to that name (for example `tezgah-standard`). Never use the\n"
    "generic `task` agent and never pick another tezgah-* agent instead of the\n"
    "routed one. Brief it with the absolute paths, the exact change and the check\n"
    "to run. You read, decide and verify: when the worker reports, run the checks\n"
    "yourself and re-brief the same routed agent on a miss. This holds for a\n"
    "one-line fix too." % ROUTE)


def deploy(out: pathlib.Path) -> None:
    """The installed agent dir without its per-run state, symlinks preserved."""
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(SOURCE, out, symlinks=True, ignore=shutil.ignore_patterns(*RUN_STATE))


def pin_overrides(config: str, model: str) -> tuple[str, int]:
    """`config.yml` with every `task.agentModelOverrides` value set to `model`;
    no other line is touched."""
    if not re.fullmatch(MODEL_ID, model):
        raise SystemExit("ARMBENCH_SUBAGENT_MODEL=%r is not a model id: it must match %s"
                         % (model, MODEL_ID))
    block = re.search(r"(?m)^task:\n(?:  .*\n)*?  agentModelOverrides:\n((?:    [\w-]+: .*\n?)+)",
                      config)
    if not block:
        raise SystemExit("no task.agentModelOverrides block in %s to pin" % (SOURCE / "config.yml"))
    pinned, n = re.subn(r"(?m)^(    [\w-]+: ).*$", lambda m: m.group(1) + '"%s"' % model,
                        block.group(1))
    return config[:block.start(1)] + pinned + config[block.end(1):], n


def render_agents() -> dict:
    """{filename: text} for agents/, from this checkout's hooks/tezgah_agents.py."""
    sys.path.insert(0, str(ROOT.parents[1] / "hooks"))
    import tezgah_agents
    return tezgah_agents.omp_user_agents("~")


def delegate(name: str, text: str) -> dict:
    """The files that make `name` from the installed dir, every input checked."""
    config, n = pin_overrides((SOURCE / "config.yml").read_text(encoding="utf-8"), SUBAGENT_MODEL)
    agents = render_agents()
    if not agents:
        raise SystemExit("%s: hooks/tezgah_agents.py rendered no agent" % name)
    provenance = (
        "# %s\n\nThe installed omp agent dir `%s` with one paragraph appended to\n"
        "`RULES.md` (below), %d subagent model overrides in `config.yml` pinned to\n"
        "`%s`, and `agents/` rendered by this checkout's `hooks/tezgah_agents.py`.\n"
        "Regenerate with\n`ARMBENCH_SUBAGENT_MODEL=%s python3 make_variants.py %s`\n"
        "in this directory.\n\n---\n\n%s\n" % (name, SOURCE, n, SUBAGENT_MODEL, SUBAGENT_MODEL,
                                               name, DELEGATE))
    files = {"RULES.md": text.rstrip("\n") + "\n\n" + DELEGATE + "\n", "config.yml": config,
             "PROVENANCE.md": provenance}
    files.update({"agents/" + f: body for f, body in agents.items()})
    return {"files": files, "agents": True,
            "line": "%-20s delegate paragraph, %d overrides pinned to %s"
                    % (name, n, SUBAGENT_MODEL)}


def ablate(name: str, lead: str, text: str) -> dict:
    paragraphs = text.split("\n\n")
    kept = [p for p in paragraphs if not p.lstrip().startswith(lead)]
    if len(kept) == len(paragraphs):
        raise SystemExit("%s: no paragraph starts with %r" % (name, lead))
    removed = [p for p in paragraphs if p.lstrip().startswith(lead)][0]
    ablated = "\n\n".join(kept)
    # a header naming what this arm is missing, so a run log identifies the arm
    provenance = (
        "# %s\n\n"
        "The installed omp agent dir `%s` with one clause removed from `RULES.md`,\n"
        "so the arm differs from `omp+tezgah` in the contract alone: the copied\n"
        "`hooks/pre/tezgah-hook.ts` is the installed byte and pins the same checkout,\n"
        "and every other copied file is the installed byte too. Regenerate with\n"
        "`python3 make_variants.py` in this directory, which re-copies the installed\n"
        "dir and rewrites this file - the two committed files here are the contract\n"
        "and this header, and the rest of the arm is the deployment.\n\n"
        "Copied: everything that dir holds except per-run state (`sessions/`, `blobs/`,\n"
        "`cache/`, `terminal-sessions/`, `custom-session-files/`, `*.db*`,\n"
        "`config.yml.lock`), which omp recreates on first run. `skills/` is copied as\n"
        "symlinks and still resolves into the primary checkout. `arms.json` gives the\n"
        "arm the same `TEZGAH_ROOTS` as `omp+tezgah`: without it `tezgah_paths.root_for`\n"
        "answers None for a run directory under the bench root, every hook returns\n"
        "early, and the arm is inert however complete this directory is.\n\n"
        "The ablated `RULES.md` is %d bytes against the installed %d, both read by this\n"
        "generator; `const HOOK` is unchanged, so the harness the arm loads is the\n"
        "primary checkout's at generation time and the arm is not pinned to a commit.\n"
        "That omp itself loads this directory at runtime is not verified here: no row\n"
        "has been scored on these arms, and the positive control needs a paid run.\n\n"
        "---\n\n%s\n"
        % (name, SOURCE, len(ablated), len(text), removed))
    return {"files": {"RULES.md": ablated, "PROVENANCE.md": provenance}, "agents": False,
            "line": "%-20s removed %d chars, contract now %d chars"
                    % (name, len(removed), len(ablated))}


def main(argv) -> int:
    unknown = [a for a in argv if a not in CLAUSES and a not in DELEGATE_ARMS]
    if unknown:
        raise SystemExit("unknown arm: %s (known: %s)"
                         % (", ".join(unknown), ", ".join([*CLAUSES, *DELEGATE_ARMS])))
    contract = SOURCE / "RULES.md"
    if not contract.exists():
        raise SystemExit("no installed contract at %s - run tezgah-setup first" % contract)
    text = contract.read_text(encoding="utf-8")
    # bare: the clause ablations only; a delegate arm is built when it is named
    names = argv or list(CLAUSES)
    plans = {name: delegate(name, text) if name in DELEGATE_ARMS else ablate(name, CLAUSES[name], text)
             for name in dict.fromkeys(names)}
    for name, plan in plans.items():
        out = ROOT / "arms" / name
        deploy(out)
        if plan["agents"]:
            shutil.rmtree(out / "agents", ignore_errors=True)
            (out / "agents").mkdir()
        for rel, body in plan["files"].items():
            (out / rel).write_text(body, encoding="utf-8")
        print(plan["line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
