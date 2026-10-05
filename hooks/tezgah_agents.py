#!/usr/bin/env python3
"""Per-repo subagent definitions, generated from the detected infrastructure.

When a session starts inside a tezgah root, the enclosing repo gets a small set
of specialized agents, rendered into every host surface that actually exists:

  Claude Code / Cursor  `.claude/agents/*.md`   (Cursor reads this dir natively)
  opencode              `.opencode/agents/*.md` (fallback) + config injection
  Codex                 `.codex/agents/*.toml`

A role is only emitted when the capability it needs is present (the reviewer
needs the code graph); the three tier workers are emitted in every root,
because `tezgah-route` names one of them for every delegated task. The whole set is regenerated when either this manifest
or the repo's infrastructure changes, so the definitions stay updatable instead
of drifting. Hosts with no such surface (dsh) get nothing here; the orchestrator
directive in the injected contract already covers them. The generated dirs are
ignored through the clone's own `info/exclude`, never through the tracked
`.gitignore`: a session must not hand the user back a modified file.

Every write fails open: a hook must never fail a session because a file could
not be written. Stdlib only.
"""
import glob
import hashlib
import json
import os
import re
import subprocess

import tezgah_models as tm
from tezgah_paths import (CONFIG_DIR, HOME, codegraph_bin, host_installed, off,
                          root_for)

MARKER = "# tezgah: managed by tezgah-agents; do not edit"
STATE = os.path.join(CONFIG_DIR, "agents.state.json")
# hosts with a file-based custom-agent surface, and where it lives, relative to
# the repo. Cursor reads .claude/agents/ natively, so one markdown dir serves
# both when either is installed; the *detection* of whether a host is installed
# lives in tezgah_paths.host_installed, not here.
FILE_HOSTS = ("claude", "opencode", "codex", "cursor")
HOST_DIRS = {"claude": os.path.join(".claude", "agents"),
             "cursor": os.path.join(".claude", "agents"),
             "opencode": os.path.join(".opencode", "agents"),
             "codex": os.path.join(".codex", "agents")}
# Stack markers -> a short hint. Exact commands are left to the repo's own docs
# so a guess never becomes a fabricated test run.
STACK_FILES = (("pyproject.toml", "python"), ("setup.py", "python"),
               ("requirements.txt", "python"), ("package.json", "node"),
               ("go.mod", "go"), ("Cargo.toml", "rust"), ("Makefile", "make"))
# The codegraph surface a brief may name: the MCP tools tezgah's server row
# enables (CODEGRAPH_MCP_TOOLS in bin/tezgah-setup; `affected` is not among
# them) and the CLI verbs a role with a shell reaches. A brief that named a tool
# outside this set would be naming a call the role cannot make.
GRAPH_TOOL = "codegraph_explore"
GRAPH_MCP = ("codegraph_explore", "codegraph_impact", "codegraph_callers",
             "codegraph_node")
# Claude names a server's tools by where it was registered: the plugin's server
# as `mcp__plugin_tezgah_codegraph__*`, a checkout's own `.mcp.json` server as
# `mcp__codegraph__*`. A select line names both, so it loads whichever exists.
MCP_PREFIXES = ("mcp__codegraph__", "mcp__plugin_tezgah_codegraph__")
GRAPH_SELECT = ",".join(p + t for t in GRAPH_MCP for p in MCP_PREFIXES)
GRAPH_CLI = ("callers", "callees", "impact", "node", "files")
GRAPH_TOOLS = ", ".join("`codegraph %s`" % verb for verb in GRAPH_CLI)
# A role with no shell (Claude `disallowedTools` Bash, opencode `bash: deny`)
# cannot run `git diff` or the CLI, so its blast radius comes from the caller's
# brief and the MCP impact tool; a role with a shell runs the diff itself.
NO_SHELL = ("claude", "opencode")
# The floor every graph role carries (gortex edge provenance): the index holds
# only the edges its parser saw, so an absence of callers is a coverage gap
# until shown otherwise, never a safety verdict.
EMPTY_IS_NOT_PROOF = (
    "An empty or short caller list is not proof that a change is safe: the\n"
    "index records only the edges its parser saw, so say what it cannot see\n"
    "(dynamic dispatch, string or config lookups, unindexed files) instead of\n"
    "implying the list is complete.")
# The task class each generated specialist is for, in the order the steering
# line names them. The orchestrator is not here: it is a primary agent, not one
# the main thread delegates to.
STEER = (("mechanical edit (tier from `tezgah-route`)", "tezgah-cheap"),
         ("bounded code or tests", "tezgah-standard"),
         ("design, invariants, unknown-cause debugging", "tezgah-frontier"),
         ("review of a diff", "tezgah-reviewer"))


def manifest_sha():
    try:
        with open(os.path.abspath(__file__), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return "unknown"


def _stack(root):
    return sorted({name for f, name in STACK_FILES if os.path.exists(os.path.join(root, f))})


def _graph_howto(host):
    if host == "claude":
        # Claude defers MCP schemas, so the tools have to be selected before the
        # first call; the role has no shell, so the MCP tools are its whole graph.
        return ('Load the graph tools first: ToolSearch("select:%s"). You have no\n'
                "shell, so the codegraph CLI is out of reach: use those MCP tools."
                % GRAPH_SELECT)
    if host == "omp":
        # omp's MCP device refuses a second session's call while another one
        # holds the index ("Concurrent write refused"), and a subagent always
        # runs beside its parent, so the CLI is the only graph it can reach.
        return ("Use the codegraph CLI through bash (%s, `codegraph query`,\n"
                "`codegraph status`). Do not call the `xd://mcp__codegraph_*`\n"
                "devices: omp refuses them with \"Concurrent write refused\"\n"
                "while the parent session holds the index." % GRAPH_TOOLS)
    if host == "opencode":
        return ("codegraph is registered as an MCP server (%s). You have no\n"
                "shell, so the codegraph CLI is out of reach: use those MCP tools."
                % ", ".join("`%s`" % t for t in GRAPH_MCP))
    return ("codegraph is registered as an MCP server (default tool\n"
            "`%s`) and the rest of the surface is the CLI (%s); use both as-is."
            % (GRAPH_TOOL, GRAPH_TOOLS))


def _blast_radius(host):
    """How the reviewer derives the blast radius on this host."""
    if host in NO_SHELL:
        return ("You have no shell, so you cannot run `git diff`: the caller passes\n"
                "the changed files and symbols of the target (a base branch, a ref or\n"
                "the PR under review). Run the MCP `codegraph_impact` tool per changed\n"
                "symbol - that is the blast radius. If the brief names no changed files,\n"
                "say so and ask for them instead of guessing.")
    return ("Take the changed files and symbols from `git diff <target>` (a base\n"
            "branch, a ref or the PR under review), then run `codegraph impact\n"
            "<symbol>` per changed symbol - that is the blast radius.\n"
            "`git diff --name-only <target> | codegraph affected --stdin` names the\n"
            "test files the change reaches.")


def _may_use(host):
    """The read-only roles' tool sentence: on omp and Codex the role has a shell,
    and the sentence bounds it to the codegraph CLI and read-only git."""
    if host in ("omp", "codex"):
        return ("You may use: read, grep, glob, and a shell for the `codegraph` CLI\n"
                "and read-only `git` (diff, log, show) only. Read-only: no writes, no\n"
                "edits, no other shell command.")
    return ("You may use: the codegraph MCP tools, read, grep and glob. Read-only:\n"
            "no writes, no edits, no shell.")


def detect_infra(root):
    """Capabilities + stack + file-surface hosts for the enclosing repo."""
    caps = {
        "graph": bool(codegraph_bin()) and not os.path.exists(
            os.path.join(root, ".no-graph")),
    }
    try:
        cfg = json.load(open(os.path.join(CONFIG_DIR, "config.json"), encoding="utf-8"))
        configured = cfg.get("hosts")
    except Exception:
        configured = None
    if configured:
        # An explicit list is the answer, even when it names no file host: omp
        # keeps its subagents user-level, and rendering .claude/.cursor files
        # for a host the user did not list is not what that list asked for.
        hosts = [h for h in configured if h in FILE_HOSTS]
    else:
        hosts = [h for h in FILE_HOSTS if host_installed(h)]
    return {"caps": caps, "stack": _stack(root), "hosts": hosts}


# ------------------------------------------------------------------ roles ----

def _reviewer_body(host):
    return (
        "You are tezgah-reviewer, an adversarial code reviewer. Review a change,\n"
        "not the whole repo, with the code graph as below.\n\n"
        "%s\n\n"
        "Review the raw artifact, never a summary of it and never the author's\n"
        "self-assessment. Format, schema, frontmatter and spec-compliance problems\n"
        "live in the exact text, and a framing you were handed is a finding you will\n"
        "not make: a reviewer given the implementer's view finds measurably fewer\n"
        "defects. If you were handed a paraphrase, read the files instead.\n\n"
        "%s Read the changed code and any caller you intend to accuse.\n"
        "%s\n"
        "Look only for defects the change causes: correctness, contract/callers,\n"
        "security, tests, concurrency and performance. Classify every candidate as\n"
        "confirmed (concrete failure scenario + file:line), refuted (a guard,\n"
        "caller contract, type or test already prevents it) or unverified (not\n"
        "settled). Default to refuted when the evidence is unclear. Only the code\n"
        "or a run you observed settles a candidate: a doc, a comment, a lessons\n"
        "file, a memory note or an earlier report may raise a question but never\n"
        "makes it confirmed or refuted on its own. Report only confirmed findings\n"
        "as bugs; no style notes, no praise; empty is the correct answer for a\n"
        "clean change.\n\n"
        "Score the constraints separately from the defects. For every constraint\n"
        "the task stated - keep this behaviour, touch no other file, preserve this\n"
        "format - report kept or violated with the file:line that shows which. A\n"
        "patch that passes the tests and breaks a stated constraint is not clean,\n"
        "and a functional test will not notice it.\n\n"
        "Every finding carries a severity - critical (the change cannot stand as\n"
        "written), major (a real weakness that must be fixed), minor (noticeable),\n"
        "suggestion (an improvement, not a flaw) - and a verbatim quote of the\n"
        "code it accuses; a finding about an absence carries no quote. A severity\n"
        "is lowered only by evidence: a check you could not complete never\n"
        "downgrades a confirmed finding - keep its severity and mark it\n"
        "provisional. Disclose the order you read the files in.\n\n"
        "Scope and budget. Every round that confirms a defect is followed by a\n"
        "round over that fix's delta; the review ends when a round confirms none.\n"
        "A later round reads only the delta since the sha the previous round\n"
        "recorded (`tezgah-task review` prints it): re-reading the whole diff\n"
        "re-reports what was already triaged. Test results are input, not a task\n"
        "- read the author's output file; do not run the suite, and run at most one\n"
        "`-k` test when a specific accusation needs it. The same defect family\n"
        "confirmed three times is a sign the design needs a pivot, not another\n"
        "patch.\n\n"
        "%s" % (_graph_howto(host), _blast_radius(host), EMPTY_IS_NOT_PROOF,
                _may_use(host)))


def _worker_body(tier):
    def body(_host):
        if tier == "frontier":
            scope = ("You take the work the cheaper tiers must not: design choices,\n"
                     "stored-data and ordering invariants, security-sensitive code,\n"
                     "failures with an unknown cause, hard-to-reverse changes.")
        else:
            scope = ("If the work needs a judgement above this tier - a design choice,\n"
                     "a stored-data or ordering invariant, security-sensitive code, or\n"
                     "a failure whose cause you cannot find - stop editing and answer\n"
                     "`ESCALATE: <why>`; the router restarts it on tezgah-frontier.")
        return ("You are tezgah-%s, a worker on the %s model tier. Do exactly the\n"
                "brief: stay inside the files it names, run the checks it names, and\n"
                "report what changed and what each check printed, verbatim. Report\n"
                "progress, but never redefine the work. Never widen or narrow the brief's\n"
                "scope, budget or question. If the brief cannot be met as written, say\n"
                "so and stop rather than answering a different question.\n%s\n"
                "Never spawn subagents." % (tier, tier, scope))
    return body


# name, description, capability gate, body(host), read-only?
ROLES = (
    ("tezgah-reviewer",
     "Adversarial, read-only review of a diff, branch or PR: derives the blast "
     "radius, checks correctness, contract, security, tests and performance, and "
     "classifies every finding confirmed/refuted/unverified.",
     lambda infra: infra["caps"]["graph"], _reviewer_body, True),
    ("tezgah-cheap",
     "Mechanical, fully specified edits on the cheapest model tier: renames, "
     "fixtures, formatting, version bumps, commit messages, a listed migration. "
     "Chosen by `tezgah-route`; answers ESCALATE when the work needs judgement.",
     lambda infra: True, _worker_body("cheap"), False),
    ("tezgah-standard",
     "Bounded code, tests, search-and-summarise or a small review on the standard "
     "model tier. Chosen by `tezgah-route`; answers ESCALATE when the work needs "
     "judgement above it.",
     lambda infra: True, _worker_body("standard"), False),
    ("tezgah-frontier",
     "Design, stored-data or ordering invariants, security-sensitive code, "
     "unknown-cause debugging and hard-to-reverse changes on the strongest model "
     "tier; also where an ESCALATE from a cheaper worker is restarted.",
     lambda infra: True, _worker_body("frontier"), False),
)

# The roles gated on the code graph, which a repo's `.no-graph` turns off.
GRAPH_ROLES = ("tezgah-reviewer",)

ORCH_DESC = ("Route work in this repo to the generated tezgah-* subagents. The "
             "main thread decides and verifies; delegate bounded, well-specified "
             "work and never let a subagent orchestrate another.")


def _orch_body(names):
    listed = ", ".join(names) if names else "(none active yet)"
    return (
        "You are the tezgah orchestrator for this repository. You decide and\n"
        "verify; you delegate bounded, well-specified work and read the evidence\n"
        "back. Available specialists: %s.\n\n"
        "Route reviews to tezgah-reviewer, with the changed files and symbols in\n"
        "the brief: where it has no shell it cannot run `git diff` itself. Brief a\n"
        "code-discovery task to a tier worker with the codegraph tools; a second\n"
        "opinion (`consult`) and research (`orx`) stay with the main thread. Other\n"
        "work goes to the tier worker\n"
        "`tezgah-route \"<brief>\"` names (tezgah-cheap, tezgah-standard,\n"
        "tezgah-frontier); an ESCALATE answer is restarted on tezgah-frontier with\n"
        "the same brief. Never delegate a task a specialist is not\n"
        "listed for, and never let a subagent spawn its own subagents. Verify each\n"
        "returned claim against the code before acting." % listed)


# ---------------------------------------------------------------- renderers --

# Claude Code's own aliases: an alias follows the provider (and keeps the main
# session's variant and context), while a full id breaks on Bedrock, Vertex and
# a gateway (code.claude.com/docs/en/sub-agents, model/effort table).
CLAUDE_ALIAS = (("claude-opus", "opus"), ("claude-sonnet", "sonnet"),
                ("claude-haiku", "haiku"), ("claude-fable", "fable"))


def _claude_model(model):
    for prefix, alias in CLAUDE_ALIAS:
        if model.startswith(prefix):
            return alias
    return model


def _model_lines(name, family, model_fmt, effort_fmt):
    """The model (and effort) lines the table gives this agent on a family;
    `model: inherit` on Claude/Cursor for an agent with no slot. Cursor reads
    this same file but wants its own ids and the effort inside the id
    (`claude-opus-5[effort=high]`, cursor.com/docs/subagents) - unverified for
    the ids this table names, so Cursor is documented, not guessed at."""
    picked = tm.pick(name, family)
    if not picked:
        return ["model: inherit"] if family == "anthropic" else []
    model, effort = picked
    if family == "anthropic":
        model = _claude_model(model)
    return [model_fmt % model] + ([effort_fmt % effort] if effort else [])


def _fold(desc, width=74):
    out = []
    for chunk in re.findall(r".{1,%d}(?:\s|$)" % width, desc.strip()):
        if chunk.strip():
            out.append("  " + chunk.strip())
    return out or ["  " + desc.strip()]


def render_md(name, description, readonly, body):
    """Claude Code / Cursor markdown. Cursor ignores unknown keys and honours
    `readonly`; Claude denies the write/shell tools explicitly."""
    lines = ["---", MARKER + " (manifest %s)" % manifest_sha(),
             "name: %s" % name, "description: >"]
    lines += _fold(description)
    lines += _model_lines(name, "anthropic", "model: %s", "effort: %s")
    if readonly:
        # `disallowedTools` is Claude's; `readonly` is Cursor's. Both parsers
        # ignore the other's field.
        lines.append("readonly: true")
        lines.append("disallowedTools: Write, Edit, NotebookEdit, Bash, Agent")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def plugin_agents():
    """{filename: text} for the plugin's own tracked `agents/` dir.

    The graph roles' Claude render, from the same body the per-repo files get,
    so the shipped copy cannot drift from the generated one. The MARKER line is
    dropped: the copy is tracked, never swept by `_remove_stale`, and its
    manifest sha would turn every edit of this module into a stale file.
    `tezgah-setup --write-plugin-agents` writes it; a test pins it."""
    out = {}
    for name, desc, _cap, body, readonly in ROLES:
        if name in GRAPH_ROLES:
            lines = render_md(name, desc, readonly, body("claude")).split("\n")
            out[name + ".md"] = "\n".join(lines[:1] + lines[2:])
    return out


def render_md_opencode(name, description, readonly, body):
    """opencode `.opencode/agents/*.md`. opencode validates `tools` as an object
    (the Claude `Agent(...)` string is rejected), so this uses opencode's own
    `mode` + `permission` keys and never emits a `tools` string."""
    lines = ["---", MARKER + " (manifest %s)" % manifest_sha(),
             "name: %s" % name, "description: >"]
    lines += _fold(description)
    lines.append("mode: subagent")
    if tm.opencode_model(name):
        lines.append("model: %s" % tm.opencode_model(name))
    if readonly:
        lines += ["permission:", "  edit: deny", "  bash: deny", "  task: deny"]
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def _toml_str(s):
    """A literal multi-line TOML string, safe for our controlled bodies."""
    return "'''" + s.replace("'''", "''\\'") + "'''"


def render_md_omp(name, description, body, tools=("read", "grep", "glob", "bash")):
    """omp subagent markdown: name/description frontmatter plus a tool list.

    omp has no `readonly` key. Every role gets bash: the read-only ones are the
    graph roles, whose graph on omp is the `codegraph` CLI (see _graph_howto),
    and their body bounds the shell to that CLI."""
    lines = ["---", "name: %s" % name, "description: >"]
    lines += _fold(description)
    if tools:  # None: every tool the session has (a tier worker edits)
        lines.append("tools:")
        lines += ["  - %s" % t for t in tools]
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def omp_user_agents(root="~"):
    """{filename: text} for omp's user agent dir (~/.omp/agent/agents)."""
    infra = detect_infra(os.path.expanduser(root))
    active = [r for r in ROLES if r[2](infra)]
    names = [r[0] for r in active]
    if not names:
        return {}
    out = {name + ".md": render_md_omp(
        name, desc, body("omp"),
        **({"tools": None} if name[len("tezgah-"):] in tm.TIERS else {}))
           for name, desc, _cap, body, _readonly in active}
    out["tezgah-orchestrator.md"] = render_md_omp(
        "tezgah-orchestrator", ORCH_DESC, _orch_body(names),
        tools=("read", "grep", "glob", "bash", "task"))
    return out


def steering(root, host=None):
    """One line naming the generated specialists this host can spawn, or None.

    Nothing else in the contract points the main agent at them, so a model
    reached for the host's generic explorer instead. Existence is read from
    disk, not from the capabilities: a specialist is named only when its file
    is there for the host to load - omp's user agent dir on omp, the repo's
    generated dirs everywhere else. A repo's `.no-graph` turns the graph off
    there, so a graph role is not named in it even when omp's user-level file
    exists."""
    if host == "omp":
        dirs = [os.path.join(HOME, ".omp", "agent", "agents")]
    else:
        dirs = [os.path.join(root, d) for d in set(HOST_DIRS.values())]
    have = {os.path.splitext(os.path.basename(p))[0]
            for d in dirs for p in glob.glob(os.path.join(d, "tezgah-*.*"))}
    if os.path.exists(os.path.join(root, ".no-graph")):
        have -= set(GRAPH_ROLES)
    pairs = ["%s -> %s" % (task, name) for task, name in STEER if name in have]
    if not pairs:
        return None
    return ("Specialists for this host: %s. Spawn them by name instead of a "
            "generic explorer or task agent." % "; ".join(pairs))


def render_toml(name, description, readonly, body):
    """Codex `.codex/agents/*.toml` (name/description/developer_instructions)."""
    lines = [MARKER + " (manifest %s)" % manifest_sha(),
             'name = "%s"' % name,
             "description = " + _toml_str(description)]
    lines += _model_lines(name, "openai", 'model = "%s"', 'model_reasoning_effort = "%s"')
    if readonly:
        lines.append('sandbox_mode = "read-only"')
    lines.append("developer_instructions = " + _toml_str(body.strip()))
    return "\n".join(lines) + "\n"


def render_orch_md(names):
    tools = ", ".join(names) if names else "Read, Grep, Glob"
    fm = ("---\n%s (manifest %s)\nname: tezgah-orchestrator\n"
          "description: %s\nmodel: inherit\ntools: Agent(%s), Read, Grep, Glob\n---\n"
          % (MARKER, manifest_sha(), ORCH_DESC, tools))
    return fm + "\n" + _orch_body(names) + "\n"


def render_orch_md_opencode(names):
    fm = ("---\n%s (manifest %s)\nname: tezgah-orchestrator\n"
          "description: %s\nmode: primary\n"
          "permission:\n  task:\n    \"*\": deny\n    \"tezgah-*\": allow\n---\n"
          % (MARKER, manifest_sha(), ORCH_DESC))
    return fm + "\n" + _orch_body(names) + "\n"


def orch_opencode_entry(names):
    return {"description": ORCH_DESC, "mode": "primary", "prompt": _orch_body(names),
            "permission": {"task": {"*": "deny", "tezgah-*": "allow"}}}


def _role_oc_entry(name, desc, body, readonly):
    entry = {"description": desc, "mode": "subagent", "prompt": body}
    if tm.opencode_model(name):
        entry["model"] = tm.opencode_model(name)
        picked = tm.pick(name, "any")
        if picked and picked[1]:
            # the JSON agent config is where opencode documents the effort
            # (opencode.ai/docs/agents, `reasoningEffort`)
            entry["reasoningEffort"] = picked[1]
    if readonly:
        entry["permission"] = {"edit": "deny", "bash": "deny", "task": "deny"}
    return entry


# ------------------------------------------------------------------- sync ----

def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _is_managed(text):
    return bool(text) and MARKER in text


def _write_if_changed(path, text):
    """True when the file changed. Fails open, as the module promises: a hook
    must never fail a session because a file could not be written."""
    if _read(path) == text:
        return False
    tmp = path + ".tezgah-tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)      # os.replace onto a directory leaves it behind
        except OSError:
            pass
        return False
    return True


def _remove_stale(directory, wanted):
    """Delete only tezgah-managed files no longer in the wanted set."""
    for path in glob.glob(os.path.join(directory, "tezgah-*.*")):
        if os.path.basename(path) not in wanted and _is_managed(_read(path)):
            try:
                os.remove(path)
            except OSError:
                pass


BLOCK_BEGIN = ("# tezgah: generated agents (managed; removed by "
               "tezgah-setup --uninstall)")
BLOCK_END = "# tezgah: end generated agents"


def _strip_block(text):
    out, skip = [], False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == BLOCK_BEGIN:
            skip = True
            continue
        if stripped == BLOCK_END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "".join(out)


def _block_dirs(text):
    """The dir names already inside the managed block of `text`."""
    out, inside = set(), False
    for line in text.splitlines():
        s = line.strip()
        if s == BLOCK_BEGIN:
            inside = True
        elif s == BLOCK_END:
            inside = False
        elif inside and s.startswith("/") and s.endswith("/"):
            out.add(s.strip("/"))
    return out


def _put_block(old, block):
    """Put the managed block where it already is, or append it at the end.

    Rebuilding the file around the block used to move it to the end of any file
    whose block sat mid-file, so the first session start in a fresh checkout
    dirtied the tree with a pure move. Replacing it in place keeps the user's
    ordering, and the caller's `new != old` check then writes nothing."""
    out, inside, replaced = [], False, False
    for line in old.splitlines():
        s = line.strip()
        if s == BLOCK_BEGIN:
            inside, replaced = True, True
            out.extend(block.splitlines())
            continue
        if s == BLOCK_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    if not replaced:
        body = "\n".join(out).strip("\n")
        return (body + "\n\n" if body else "") + block
    return "\n".join(out).strip("\n") + "\n"


def _exclude_path(root):
    """The clone's own `info/exclude`, or None when `root` is not a git tree.

    A plain checkout answers from the directory listing, so a session start
    keeps its two git forks; a linked worktree or submodule (`.git` is a file)
    asks git, which resolves the path through the common dir - the file git
    actually reads, not a per-worktree path it ignores. GIT_DIR/GIT_WORK_TREE
    move the repository out from under that listing, so a set environment means
    only git can answer."""
    dot = os.path.join(root, ".git")
    if (os.path.isdir(dot) and not os.environ.get("GIT_DIR")
            and not os.environ.get("GIT_WORK_TREE")):
        return os.path.join(dot, "info", "exclude")
    if not os.path.exists(dot) and not os.environ.get("GIT_DIR"):
        return None
    try:
        out = subprocess.run(("git", "-C", root, "rev-parse", "--git-path",
                              "info/exclude"),
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    path = out.stdout.strip()
    if out.returncode != 0 or not path:
        return None
    return path if os.path.isabs(path) else os.path.join(root, path)


def ensure_exclude(root, dirs):
    """Ignore the generated agent dirs in the clone's own exclude file.

    NOT in `.gitignore`: that file is tracked, so writing it handed the user a
    repository back with a modification nobody asked for. `info/exclude` is
    per-clone, never committed and still keeps `git status` clean, which is all
    the ignore line was ever for. The block is a UNION with what is already
    there: a dir ignored by an earlier install keeps its line even when its host
    is not in the current set, so a config change can never un-ignore a
    generated-agent dir. Returns the exclude path, or None when opted out with
    TEZGAH_NO_EXCLUDE=1, when the root is not a git work tree, or when there is
    nothing to ignore."""
    if os.environ.get("TEZGAH_NO_EXCLUDE") == "1":
        return None
    path = _exclude_path(root)
    if not path:
        return None
    old = _read(path) or ""
    dirs = sorted(set(d for d in dirs if d) | _block_dirs(old))
    if not dirs:
        return None
    block = "\n".join([BLOCK_BEGIN] + ["/" + d + "/" for d in dirs]
                      + [BLOCK_END]) + "\n"
    new = _put_block(old, block)
    _write_if_changed(path, new)
    return path


def sync_root(root, report_steady=False):
    """Generate/refresh this repo's agents.

    Returns a one-line status - a write, a removal, or, only when
    `report_steady`, "N agent(s) current". A steady state returns None by
    default because the session hook injects this line: a session that changed
    nothing was being told about tezgah's own files in the repo. The explicit
    CLI asks for the steady line, since it is answering a user's command.

    Under `agents-off` nothing is generated and the sweep below still runs:
    the switch removes what an earlier session wrote, so the host stops
    loading it."""
    if not root_for(root):
        return None
    disabled = off("agents-off")
    infra = detect_infra(root)
    hosts = set() if disabled else set(infra["hosts"])
    active = [] if disabled else [r for r in ROLES if r[2](infra)]
    names = [r[0] for r in active]

    # markdown: one dir serves Claude and Cursor (Cursor reads .claude/agents/)
    md_dir = os.path.join(root, HOST_DIRS["claude"]) if hosts & {"claude", "cursor"} else None
    oc_dir = os.path.join(root, HOST_DIRS["opencode"]) if "opencode" in hosts else None
    codex_dir = os.path.join(root, HOST_DIRS["codex"]) if "codex" in hosts else None

    written, removed = 0, 0
    paths = []

    def emit(directory, wanted, name, text):
        nonlocal written
        wanted.add(name)
        path = os.path.join(directory, name)
        if _write_if_changed(path, text):
            written += 1
        paths.append(path)

    wanted_md, wanted_oc, wanted_codex = set(), set(), set()

    def sweep(directory, wanted):
        nonlocal removed
        before = set(os.path.basename(p) for p in glob.glob(os.path.join(directory, "tezgah-*.*")))
        _remove_stale(directory, wanted)
        after = set(os.path.basename(p) for p in glob.glob(os.path.join(directory, "tezgah-*.*")))
        removed += len(before - after)

    if md_dir and names:  # Claude Code + Cursor
        for name, desc, _cap, body, readonly in active:
            emit(md_dir, wanted_md, name + ".md", render_md(name, desc, readonly, body("claude")))
        emit(md_dir, wanted_md, "tezgah-orchestrator.md", render_orch_md(names))

    if oc_dir and names:  # opencode
        for name, desc, _cap, body, readonly in active:
            emit(oc_dir, wanted_oc, name + ".md",
                 render_md_opencode(name, desc, readonly, body("opencode")))
        emit(oc_dir, wanted_oc, "tezgah-orchestrator.md", render_orch_md_opencode(names))

    if codex_dir and names:  # Codex (no orchestrator agent; the main thread orchestrates)
        for name, desc, _cap, body, readonly in active:
            emit(codex_dir, wanted_codex, name + ".toml",
                 render_toml(name, desc, readonly, body("codex")))

    # The sweep runs over every dir this module can write, not only the selected
    # ones: a host dropped from the config, or a capability that disappeared,
    # must not leave tezgah agents behind for the host to keep loading.
    sweep(os.path.join(root, HOST_DIRS["claude"]), wanted_md)
    sweep(os.path.join(root, HOST_DIRS["opencode"]), wanted_oc)
    sweep(os.path.join(root, HOST_DIRS["codex"]), wanted_codex)

    if paths:
        dirs = set()
        if md_dir:
            dirs.add(HOST_DIRS["claude"])
        if oc_dir:
            dirs.add(HOST_DIRS["opencode"])
        if codex_dir:
            dirs.add(HOST_DIRS["codex"])
        ex = ensure_exclude(root, dirs)
        if ex:
            paths.append(ex)
        _record(root, paths)
    # A steady-state session stays silent about the files tezgah keeps in this
    # repo: the "N agent(s) current" line rode into every session brief and read
    # as work tezgah was asking for. Only a change is worth a line.
    if written:
        return ("%d agent(s) written%s"
                % (len(names), ", %d removed" % removed if removed else ""))
    if removed:
        return "%d stale agent file(s) removed" % removed
    if report_steady and names and (md_dir or oc_dir or codex_dir):
        return "%d agent(s) current" % len(names)
    return None


def opencode_agents_json(root):
    """The active roles as opencode `config.agent` entries, or {}.

    The opencode plugin calls this at config load (via `tezgah-agents --json`) so
    the generated agents exist in the SAME session, not only the next one."""
    if off("agents-off") or not root_for(root):
        return {}
    infra = detect_infra(root)
    if "opencode" not in infra["hosts"]:
        return {}
    active = [r for r in ROLES if r[2](infra)]
    names = [r[0] for r in active]
    if not names:
        return {}
    agent = {r[0]: _role_oc_entry(r[0], r[1], r[3]("opencode"), r[4]) for r in active}
    agent["tezgah-orchestrator"] = orch_opencode_entry(names)
    return {"agent": agent}


def _record(root, paths):
    """Remember generated paths so --uninstall can remove exactly them."""
    try:
        data = json.load(open(STATE, encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    slug = re.sub(r"[^A-Za-z0-9]+", "-", os.path.realpath(root)).strip("-")
    data[slug] = sorted(set(paths))
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, STATE)
    except OSError:
        pass


def cleanup():
    """--uninstall: remove every tezgah-generated agent file, keep user files."""
    try:
        data = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return 0
    removed = 0
    for paths in (data.values() if isinstance(data, dict) else []):
        for path in paths:
            text = _read(path)
            if text and BLOCK_BEGIN in text:
                # the exclude file, or a .gitignore an older install edited:
                # strip tezgah's block and keep every line the user owns
                rest = _strip_block(text).strip("\n")
                try:
                    if rest:
                        with open(path, "w", encoding="utf-8") as fh:
                            fh.write(rest + "\n")
                    else:
                        os.remove(path)
                    removed += 1
                except OSError:
                    pass
                continue
            if _is_managed(text):
                try:
                    os.remove(path)
                    removed += 1
                except OSError:
                    pass
    try:
        os.remove(STATE)
    except OSError:
        pass
    return removed
