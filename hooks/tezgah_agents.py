#!/usr/bin/env python3
"""Per-repo subagent definitions, generated from the detected infrastructure.

When a session starts inside a tezgah root, the enclosing repo gets a small set
of specialized agents, rendered into every host surface that actually exists:

  Claude Code / Cursor  `.claude/agents/*.md`   (Cursor reads this dir natively)
  opencode              `.opencode/agents/*.md` (fallback) + config injection
  Codex                 `.codex/agents/*.toml`

A role is only emitted when the capability it needs is present (the code graph,
orx, or the consult key). The whole set is regenerated when either this manifest
or the repo's infrastructure changes, so the definitions stay updatable instead
of drifting. Hosts with no such surface (dsh) get nothing here; the orchestrator
directive in the injected contract already covers them.

Every write fails open: a hook must never fail a session because a file could
not be written. Stdlib only.
"""
import glob
import hashlib
import json
import os
import re

from tezgah_paths import (CONFIG_DIR, cbm_bin, have_consult_key, off, orx_bin,
                          root_for, tool)

MARKER = "# tezgah: managed by tezgah-agents; do not edit"
STATE = os.path.join(CONFIG_DIR, "agents.state.json")
# hosts with a file-based custom-agent surface, and where it lives, relative to
# the repo. Cursor's own dir takes precedence over .claude/, but it also reads
# .claude/agents/, so one markdown dir serves both when either is installed.
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
GRAPH_TOOLS = ("search_graph, trace_path, search_code, get_code_snippet, "
               "get_architecture, query_graph, check_index_coverage")


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
        return ('Load the graph tools first: ToolSearch("select:mcp__codebase-memory-mcp__'
                "search_graph,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__"
                "search_code,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__"
                "get_architecture,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__"
                'check_index_coverage").')
    return ("The codebase-memory-mcp tools (%s) are exposed directly; use them as-is."
            % GRAPH_TOOLS)


def detect_infra(root):
    """Capabilities + stack + file-surface hosts for the enclosing repo."""
    caps = {
        "cbm": bool(cbm_bin()) and not os.path.exists(os.path.join(root, ".no-cbm")),
        "orx": bool(orx_bin()),
        "consult": have_consult_key(),
    }
    try:
        cfg = json.load(open(os.path.join(CONFIG_DIR, "config.json")))
        hosts = [h for h in (cfg.get("hosts") or []) if h in FILE_HOSTS]
    except Exception:
        hosts = []
    if not hosts:
        home = os.path.expanduser("~")
        hosts = [h for h in FILE_HOSTS
                 if os.path.isdir(os.path.join(home, HOST_DIRS[h].split(os.sep)[0]))]
    return {"caps": caps, "stack": _stack(root), "hosts": hosts}


# ------------------------------------------------------------------ roles ----

def _explorer_body(host):
    return (
        "You are tezgah-explorer, a read-only code-discovery agent. Answer\n"
        "structural questions from evidence, never from memory or guesswork.\n\n"
        "%s\n\n"
        "Match tool to question: callers -> trace_path(direction=\"inbound\");\n"
        "callees -> trace_path(direction=\"outbound\"); definitions -> search_graph;\n"
        "exact source -> get_code_snippet; orientation -> get_architecture;\n"
        "multi-hop -> query_graph; literal text -> search_code.\n\n"
        "Rules: the graph beats grep for structure; use Read/Grep/Glob only for\n"
        "literal text the graph does not model and say it was a text search. Every\n"
        "claim carries file:line; never invent a symbol, caller or result. Disclose\n"
        "coverage gaps (unindexed files, truncation, graph blind spots). If the repo\n"
        "is not indexed, say so and stop. Read-only: no writes, edits or shell.\n\n"
        "Return the direct answer first in one or two sentences, then file:line\n"
        "evidence, then a one-line Coverage note." % _graph_howto(host))


def _reviewer_body(host):
    return (
        "You are tezgah-reviewer, an adversarial code reviewer. Review a change,\n"
        "not the whole repo. Load detect_changes and the graph tools.\n\n"
        "%s\n\n"
        'Run detect_changes(scope="impact", direction="inbound") for the target\n'
        "(base branch, ref or PR). That is the blast radius; read the changed code\n"
        "and any caller you intend to accuse. Look only for defects the change\n"
        "causes: correctness, contract/callers, security, tests, concurrency and\n"
        "performance. Classify every candidate as confirmed (concrete failure\n"
        "scenario + file:line), refuted (a guard, caller contract, type or test\n"
        "already prevents it) or unverified (not settled). Default to refuted when\n"
        "the evidence is unclear. Report only confirmed findings as bugs; no style\n"
        "notes, no praise; empty is the correct answer for a clean change. Disclose\n"
        "coverage and caps. Read-only: no writes, edits or shell." % _graph_howto(host))


def _researcher_body(_host):
    orx = orx_bin() or "orx"
    return (
        "You are tezgah-researcher, a research agent. Drive research through the\n"
        "OpenResearch CLI (`%s`): load its manual first (`%s skill`) and follow its\n"
        "experiment-tree rules instead of improvising the protocol. Use it for a\n"
        "literature/reference review, forming and testing hypotheses, or producing a\n"
        "research artifact. Do not use it for plain code discovery (that is the\n"
        "graph-first explorer). If `%s` is missing, say the research tooling is\n"
        "unavailable and fall back to a bounded host subagent. Report commands run\n"
        "and observed output; never claim a result you did not see."
        % (orx, orx, orx))


def _verifier_body(_host):
    consult = tool("consult")
    return (
        "You are tezgah-verifier. On a non-trivial or hard-to-reverse call, get an\n"
        "independent second opinion before the decision is committed. Run\n"
        "`%s \"<self-contained English question incl. options, constraints\n"
        "and what would falsify each>\"` and report which models agreed or disagreed.\n"
        "Treat the answers as advisory and verify each against the code; never adopt\n"
        "an unverified claim. If no key or models exist, say the second opinion was\n"
        "skipped and why. Skip trivial local edits."
        % consult)


# name, description, capability gate, body(host), read-only?
ROLES = (
    ("tezgah-explorer",
     "Read-only code discovery from the codebase-memory-mcp graph: definitions, "
     "callers, blast radius, architecture. Use for structural \"where/who calls\" "
     "questions in an indexed repo.",
     lambda infra: infra["caps"]["cbm"], _explorer_body, True),
    ("tezgah-reviewer",
     "Adversarial, read-only review of a diff, branch or PR: derives the blast "
     "radius, checks correctness, contract, security, tests and performance, and "
     "classifies every finding confirmed/refuted/unverified.",
     lambda infra: infra["caps"]["cbm"], _reviewer_body, True),
    ("tezgah-researcher",
     "Research and hypothesis work driven through the OpenResearch CLI; "
     "literature review, experiments, research artifacts.",
     lambda infra: infra["caps"]["orx"], _researcher_body, False),
    ("tezgah-verifier",
     "Independent second opinion via the tezgah `consult` CLI before a "
     "hard-to-reverse decision; reports which models agreed or disagreed.",
     lambda infra: infra["caps"]["consult"], _verifier_body, False),
)

ORCH_DESC = ("Route work in this repo to the generated tezgah-* subagents. The "
             "main thread decides and verifies; delegate bounded, well-specified "
             "work and never let a subagent orchestrate another.")


def _orch_body(names):
    listed = ", ".join(names) if names else "(none active yet)"
    return (
        "You are the tezgah orchestrator for this repository. You decide and\n"
        "verify; you delegate bounded, well-specified work and read the evidence\n"
        "back. Available specialists: %s.\n\n"
        "Route code discovery and blast radius to tezgah-explorer, reviews to\n"
        "tezgah-reviewer, research to tezgah-researcher, and a pre-commit second\n"
        "opinion to tezgah-verifier. Never delegate a task a specialist is not\n"
        "listed for, and never let a subagent spawn its own subagents. Verify each\n"
        "returned claim against the code before acting." % listed)


# ---------------------------------------------------------------- renderers --

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
    lines.append("model: inherit")
    if readonly:
        # `disallowedTools` is Claude's; `readonly` is Cursor's. Both parsers
        # ignore the other's field.
        lines.append("readonly: true")
        lines.append("disallowedTools: Write, Edit, NotebookEdit, Bash, Agent")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def render_md_opencode(name, description, readonly, body):
    """opencode `.opencode/agents/*.md`. opencode validates `tools` as an object
    (the Claude `Agent(...)` string is rejected), so this uses opencode's own
    `mode` + `permission` keys and never emits a `tools` string."""
    lines = ["---", MARKER + " (manifest %s)" % manifest_sha(),
             "name: %s" % name, "description: >"]
    lines += _fold(description)
    lines.append("mode: subagent")
    if readonly:
        lines += ["permission:", "  edit: deny", "  bash: deny", "  task: deny"]
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def _toml_str(s):
    """A literal multi-line TOML string, safe for our controlled bodies."""
    return "'''" + s.replace("'''", "''\\'") + "'''"


def render_md_omp(name, description, readonly, body, tools=None):
    """omp subagent markdown: name/description frontmatter plus a tool list.

    omp has no `readonly` key, so a read-only role gets a read-only tool set."""
    if tools is None:
        tools = (["read", "grep", "glob"] if readonly
                 else ["read", "grep", "glob", "bash"])
    lines = ["---", "name: %s" % name, "description: >"]
    lines += _fold(description)
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
    out = {name + ".md": render_md_omp(name, desc, readonly, body("omp"))
           for name, desc, _cap, body, readonly in active}
    out["tezgah-orchestrator.md"] = render_md_omp(
        "tezgah-orchestrator", ORCH_DESC, False, _orch_body(names),
        tools=["read", "grep", "glob", "bash", "task"])
    return out


def render_toml(name, description, readonly, body):
    """Codex `.codex/agents/*.toml` (name/description/developer_instructions)."""
    lines = [MARKER + " (manifest %s)" % manifest_sha(),
             'name = "%s"' % name,
             "description = " + _toml_str(description)]
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


def _role_oc_entry(desc, body, readonly):
    entry = {"description": desc, "mode": "subagent", "prompt": body}
    if readonly:
        entry["permission"] = {"edit": "deny", "bash": "deny", "task": "deny"}
    return entry


# ------------------------------------------------------------------- sync ----

def _read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


def _is_managed(text):
    return bool(text) and MARKER in text


def _write_if_changed(path, text):
    if _read(path) == text:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tezgah-tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return True


def _remove_stale(directory, wanted):
    """Delete only tezgah-managed files no longer in the wanted set."""
    for path in glob.glob(os.path.join(directory, "tezgah-*.*")):
        if os.path.basename(path) not in wanted and _is_managed(_read(path)):
            try:
                os.remove(path)
            except OSError:
                pass


GITIGNORE_BEGIN = ("# tezgah: generated agents (managed; removed by "
                   "tezgah-setup --uninstall)")
GITIGNORE_END = "# tezgah: end generated agents"


def _strip_gitignore(text):
    out, skip = [], False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == GITIGNORE_BEGIN:
            skip = True
            continue
        if stripped == GITIGNORE_END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "".join(out)


def _gitignore_dirs(text):
    """The dir names already inside the managed block of `text`."""
    out, inside = set(), False
    for line in text.splitlines():
        s = line.strip()
        if s == GITIGNORE_BEGIN:
            inside = True
        elif s == GITIGNORE_END:
            inside = False
        elif inside and s.startswith("/") and s.endswith("/"):
            out.add(s.strip("/"))
    return out


def ensure_gitignore(root, dirs):
    """Ignore the generated agent dirs with one idempotent managed block.

    The block is a UNION with what is already there: a dir ignored by an earlier
    install keeps its line even when its host is not in the current set, so a
    config change can never un-ignore a generated-agent dir and leak
    machine-specific bodies into the repo. Returns the .gitignore path, or None
    when opted out with TEZGAH_NO_GITIGNORE=1 or when there is nothing to
    ignore."""
    if os.environ.get("TEZGAH_NO_GITIGNORE") == "1":
        return None
    path = os.path.join(root, ".gitignore")
    old = _read(path) or ""
    dirs = sorted(set(d for d in dirs if d) | _gitignore_dirs(old))
    if not dirs:
        return None
    body = _strip_gitignore(old).strip("\n")
    block = "\n".join([GITIGNORE_BEGIN] + ["/" + d + "/" for d in dirs]
                      + [GITIGNORE_END]) + "\n"
    new = (body + "\n\n" if body else "") + block
    if new != old:
        os.makedirs(root, exist_ok=True)
        tmp = path + ".tezgah-tmp"
        with open(tmp, "w") as fh:
            fh.write(new)
        os.replace(tmp, path)
    return path


def sync_root(root):
    """Generate/refresh this repo's agents. Returns a one-line status, or None."""
    if off("agents-off"):
        return None
    if not root_for(root):
        return None
    infra = detect_infra(root)
    hosts = set(infra["hosts"])
    if not hosts:
        return None
    active = [r for r in ROLES if r[2](infra)]
    names = [r[0] for r in active]
    if not names:
        return None

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

    def sweep(directory, wanted):
        nonlocal removed
        before = set(os.path.basename(p) for p in glob.glob(os.path.join(directory, "tezgah-*.*")))
        _remove_stale(directory, wanted)
        after = set(os.path.basename(p) for p in glob.glob(os.path.join(directory, "tezgah-*.*")))
        removed += len(before - after)

    if md_dir:  # Claude Code + Cursor
        wanted = set()
        for name, desc, _cap, body, readonly in active:
            emit(md_dir, wanted, name + ".md", render_md(name, desc, readonly, body("claude")))
        emit(md_dir, wanted, "tezgah-orchestrator.md", render_orch_md(names))
        sweep(md_dir, wanted)

    if oc_dir:  # opencode
        wanted = set()
        for name, desc, _cap, body, readonly in active:
            emit(oc_dir, wanted, name + ".md",
                 render_md_opencode(name, desc, readonly, body("opencode")))
        emit(oc_dir, wanted, "tezgah-orchestrator.md", render_orch_md_opencode(names))
        sweep(oc_dir, wanted)

    if codex_dir:  # Codex (no orchestrator agent; the main thread orchestrates)
        wanted = set()
        for name, desc, _cap, body, readonly in active:
            emit(codex_dir, wanted, name + ".toml",
                 render_toml(name, desc, readonly, body("codex")))
        sweep(codex_dir, wanted)

    if paths:
        dirs = set()
        if md_dir:
            dirs.add(HOST_DIRS["claude"])
        if oc_dir:
            dirs.add(HOST_DIRS["opencode"])
        if codex_dir:
            dirs.add(HOST_DIRS["codex"])
        gi = ensure_gitignore(root, dirs)
        if gi:
            paths.append(gi)
        _record(root, paths)
    return ("%d agent(s) %s%s" % (len(names), "written" if written else "current",
                                  ", %d removed" % removed if removed else ""))


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
    agent = {r[0]: _role_oc_entry(r[1], r[3]("opencode"), r[4]) for r in active}
    agent["tezgah-orchestrator"] = orch_opencode_entry(names)
    return {"agent": agent}


def _record(root, paths):
    """Remember generated paths so --uninstall can remove exactly them."""
    try:
        data = json.load(open(STATE))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    slug = re.sub(r"[^A-Za-z0-9]+", "-", os.path.realpath(root)).strip("-")
    data[slug] = sorted(set(paths))
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, STATE)
    except OSError:
        pass


def cleanup():
    """--uninstall: remove every tezgah-generated agent file, keep user files."""
    try:
        data = json.load(open(STATE))
    except Exception:
        return 0
    removed = 0
    for paths in (data.values() if isinstance(data, dict) else []):
        for path in paths:
            if os.path.basename(path) == ".gitignore":
                text = _read(path)
                if text and GITIGNORE_BEGIN in text:
                    rest = _strip_gitignore(text).strip("\n")
                    try:
                        if rest:
                            with open(path, "w") as fh:
                                fh.write(rest + "\n")
                        else:
                            os.remove(path)
                        removed += 1
                    except OSError:
                        pass
                continue
            if _is_managed(_read(path)):
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
