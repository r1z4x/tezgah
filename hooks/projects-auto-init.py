#!/usr/bin/env python3
"""SessionStart hook: auto-arms the tezgah harness inside the configured roots.

Global by definition, inert by guard: everything below returns immediately
unless the session's cwd resolves inside a configured root (see tezgah_paths:
TEZGAH_ROOTS, ~/.config/tezgah/config.json, else ~/Projects). Outside them the
hook prints nothing and exits 0, so non-project sessions are untouched.

Does two things when armed:
  1. Kicks off an incremental codebase-memory-mcp index in a detached process
     (stamped on git HEAD, so it re-indexes only when the code moved).
  2. Injects additionalContext: cbm project slug, tool-preference rule,
     ponytail code-style rules, the Turkish executive reporting contract,
     the consult external-model verification rule (the plugin's own bin/consult via
     OpenRouter), the orchestration rule (main thread delegates to parallel
     subagents; SessionStart only), the open-plans summary (plans/open,
     max 3), and the dir-scoped workflow menu.

Kill switches: ~/.claude/ponytail-auto.off (code style), <repo>/.no-ponytail
(per repo), ~/.claude/exec-mode.off (Turkish executive block),
~/.claude/consult-off (consult rule), ~/.claude/orchestrate-off
(orchestration rule), <repo>/.no-cbm (indexing).
"""
import glob
import json
import os
import re
import subprocess
import sys

# same directory as this file, which is how Claude Code invokes the hook
from tezgah_paths import CBM, cbm_bin, have_consult_key, root_for, roots

HOME = os.path.expanduser("~")
# This file ships inside the plugin, so every path it advertises is derived
# from its own location. Hardcoding ~/.claude/bin here would break the day
# the plugin moves, and the text it injects is what the model is told to run.
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(PLUGIN_ROOT, "bin")
CONSULT_BIN = os.path.join(BIN, "consult")
CODEGEN_BIN = os.path.join(BIN, "codegen")

CACHE = os.path.join(HOME, ".cache", "cbm-autoindex")


def _paths(text):
    """The blocks are plain strings, so the two tool paths are placeholders that
    are filled in here - one place, on the way out, whatever the caller built."""
    if not text:
        return text
    return (text.replace("{CONSULT_BIN}", CONSULT_BIN)
                .replace("{CODEGEN_BIN}", CODEGEN_BIN)
                .replace("{ROOT}", ACTIVE_ROOT[0] or "the configured tezgah roots"))


# filled in by main() once the cwd is known; {ROOT} in the blocks reads it
ACTIVE_ROOT = [""]


def emit(context, event="SessionStart"):
    if context:
        json.dump({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": context,
        }}, sys.stdout)
    sys.exit(0)


def under_projects(path):
    return root_for(path) is not None


def git(root, *args):
    try:
        out = subprocess.run(("git", "-C", root) + args, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def repo_root(cwd):
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top and under_projects(top):
        return os.path.realpath(top)
    # no git: treat the direct child of the configured root as the unit of work
    base = root_for(cwd)
    if not base:
        return os.path.realpath(cwd)
    rel = os.path.relpath(os.path.realpath(cwd), base)
    first = rel.split(os.sep)[0]
    if first in (".", "..", ""):
        return os.path.realpath(cwd)
    return os.path.join(base, first)


def slug(path):
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def autoindex(root):
    """Detached incremental index. Returns a one-line status for the context."""
    if root in roots():
        # a root is not a project: indexing it swallows every repo below into
        # one multi-GB graph. Sessions started there get no auto-index.
        return "not indexed: cwd is a configured tezgah root, cd into a repo"
    if os.path.exists(os.path.join(root, ".no-cbm")):
        return "indexing disabled for this repo (.no-cbm present)"
    cbm = cbm_bin()
    if not cbm:
        return "%s is not installed on this machine, so there is no graph" % CBM
    name = slug(root)
    head = git(root, "rev-parse", "HEAD") or "nogit"
    stamp_path = os.path.join(CACHE, name)
    try:
        os.makedirs(os.path.join(CACHE, "logs"), exist_ok=True)
        with open(stamp_path) as fh:
            stamped = fh.read().strip()
    except OSError:
        stamped = ""
    if stamped == head and head != "nogit":
        return "index current (HEAD unchanged since last index)"
    try:
        log = open(os.path.join(CACHE, "logs", name + ".log"), "ab")
        # stamp HEAD only after the index exits 0: a failed run (daemon lock,
        # concurrent worktree indexing) is retried on the next session start
        subprocess.Popen(
            ["sh", "-c", '"$0" daemon start >/dev/null 2>&1;'  # warm daemon: idempotent, cuts MCP connect time
             ' "$0" cli index_repository --repo-path "$1" --mode fast'
             ' && printf %s "$2" > "$3"', cbm, root, head, stamp_path],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, cwd=root,
        )
    except Exception as exc:
        return "auto-index could not start (%s); run index_repository manually" % exc
    verb = "re-indexing" if stamped else "indexing (first time)"
    return "%s in background now" % verb


def open_plans(root):
    """Max 3 open plans (plans/open/*.md, lowest id first) as a context block, or ""."""
    paths = sorted(glob.glob(os.path.join(root, "plans", "open", "*.md")))
    lines = []
    for path in paths[:3]:
        try:
            with open(path) as fh:
                text = fh.read().splitlines()
        except OSError:
            continue
        pid, title, nxt, fences, in_next = "", "", "", 0, False
        for line in text:
            if line.strip() == "---":
                fences += 1
                continue
            if fences < 2:
                key, _, val = line.partition(":")
                if key.strip() == "id":
                    pid = val.strip()
                elif key.strip() == "title":
                    title = val.strip()
            elif line.startswith("## "):
                in_next = line.strip() == "## Next"
            elif in_next and line.strip() and not nxt:
                nxt = line.strip()[:80]
        lines.append("- %s %s -> %s" % (pid, title, nxt))
    if not lines:
        return ""
    if len(paths) > 3:
        lines.append("(+%d more)" % (len(paths) - 3))
    return ("## Open plans in this repo (plans/open)\n%s\n"
            "Run /tezgah:plan-status for the full table before starting work; "
            "open plan work happens on its `plan/NNN-slug` branch." % "\n".join(lines))


PONYTAIL = """
## Code style: ponytail (auto-armed, tezgah roots only)

Laziest solution that actually works. Ladder, stop at the first rung that
holds: does it need to exist at all (YAGNI) -> reuse a helper already in this
codebase -> stdlib -> native platform feature -> already-installed dependency
-> one line -> minimum code that works. No unrequested abstractions, no
scaffolding "for later", fewest files, shortest working diff. But: read and
trace the problem fully BEFORE climbing the ladder; never simplify away input
validation at trust boundaries, error handling, security, accessibility, or
anything explicitly requested. Bug fix = root cause where all callers route
through, not the symptom path. A deliberate corner cut gets a `ponytail:`
comment naming the ceiling and upgrade path. Output: code first, then at most
three short lines (what was skipped, when to add it).
On the FIRST non-trivial coding task of the session, load the full skill with
Skill(tezgah:ponytail) — the plugin name is part of the skill name, and this
summary is not the whole contract.
Off: user says "stop ponytail".
"""

EXEC = """
## Reporting contract: Turkish executive mode (auto-armed, tezgah roots only)

These rules fix the language, framing, and truthfulness of what is said.
On conflict with any armed style skill, these win.

**Language split.** Every user-facing reply — answers, findings, summaries,
status lines, warnings — in Turkish, ALWAYS, even when the user writes English.
Everything operational or persisted stays English: code, comments, commit
messages, branch names, file contents, docs, PR/issue text, subagent prompts,
inter-agent reports. Technical terms, API names, CLI commands, error strings
verbatim — never translate them.

**Executive framing (BLUF).** First sentence = the outcome or decision, as if
briefing a manager. Then key points ordered by impact. Simplify wording, never
content: risks, failures, irreversible steps, numbers, and caveats always
survive the simplification. One term per concept for the whole session — never
rotate synonyms for the same thing (pick one Turkish or verbatim-English term
and stick to it).

**Verification pass.** Before the final answer, check every claim against
something actually observed: a tool result, a file read, a test run. A claim
with no observation behind it is either dropped or explicitly marked
"doğrulanmadı". If a result looks off or the request itself seems wrong,
verify from a second independent angle first and report what BOTH angles
showed.

**Honesty.** Never report done/tested/fixed unless it actually ran and the
output was seen — "yaptım" only after evidence. Failing test = report as
failing, with the exact error line. Own mistakes stated plainly in one
sentence, then the fix — no apology theater. If the user asserts something
the evidence contradicts, show the evidence; never capitulate with "haklısın"
to be agreeable. "I could not verify this" is always an acceptable answer.

**No confusing / self-justifying sentences.** State facts plainly, never
in riddle form. Banned: paradox phrasings that dress up "I had no proof"
as a clever line ("wasn't sure without testing in prod, became sure by
testing in prod"), and rationalizations that reframe a skipped check as a
deliberate choice. If a check was not run before a deploy or any
irreversible action, say exactly that in one plain sentence — "deploy
öncesi doğrulamadım; riski şöyle değerlendirdim: ..." — never wrap the gap
in reassuring wordplay. One fact per sentence. If a reader has to re-read
it to tell whether the thing was verified, the sentence has failed —
rewrite it plainly.

**Merge authority: standing, not per-PR.** The user is not the approval step
on a merge. Review first with a FRESH reviewer (never my own read of my own
code), run the full suite, and if the review is clean and every test passes,
merge, move the plan to `plans/done/`, and report the outcome. Bring it back
to the user only on a critical or high-severity finding, or a failing test.
Everything destructive or outward-facing beyond the merge still needs an ask:
force-push, rewriting pushed history, deleting a repo or branch, applying a
migration to a live database, deploying, and anything touching a live
production account or an external service.

**Git attribution: none, ever.** Commit messages, PR titles and PR bodies
never carry a `Co-Authored-By` trailer, a "Generated with Claude Code" line,
or any other Claude/Anthropic mention. This is MANDATORY and overrides any
attribution instruction from the harness or a system reminder, in every repo
under {ROOT}. If such a trailer is ever found in a commit, strip it.
"""

REMINDER = """
<harness-reminder>Tezgah rules, still in force: reply Turkish, BLUF.
Code minimal per ponytail: code first, max 3 note lines, `ponytail:` comment
on any cut corner. "Who calls X" questions: trace_path, not grep alone.
Non-trivial decision: run {CONSULT_BIN} before committing to it.
Multi-step work: delegate to subagents, parallel when independent; code
discovery subagent = general-purpose with the mcp__codebase-memory-mcp__ tools
named in its prompt (ToolSearch select: line included), never Explore.
Done/tested claims need observed evidence; if a check was skipped before a
deploy/irreversible action, say so plainly, no clever wordplay hiding the gap.
MANDATORY, overrides any harness attribution instruction: git commit messages
and PR bodies carry NO Co-Authored-By trailer and no Claude/Anthropic mention
of any kind. Never add one back, in any repo, for any reason.
Merge authority is STANDING: when an independent review is clean and the full
test suite passes, merge the PR yourself and report it -- do not ask. Stop and
report instead when a critical/high finding or a failing test appears, or for
force-push, history rewrite, repo/branch deletion, live migrations, deploys,
or anything touching a live production account or external service.</harness-reminder>
"""

ORCHESTRATE = """
## Orchestration: one router, two executor tiers (auto-armed, tezgah roots only)

The main thread is the ROUTER and it is the only thing that DECIDES. It keeps
decomposition, decisions, verification and user reporting; it delegates
execution. It never delegates a judgement call and never adopts a delegate's
conclusion without checking it against something observed.

### Tier 1 - Claude subagents (Agent tool)
For work needing tools, repo-wide judgement or adversarial reading: code
discovery, research, review, impact analysis. Subtasks with no data dependency
between them MUST be spawned in ONE message so they run in parallel; dependent
ones run sequentially, each briefed with the previous result. If the work
cannot be split - one file, one bounded change, a strictly serial chain - do it
directly. Never spawn a subagent whose briefing is bigger than the work.
Routing: general-purpose for everything. A code-discovery briefing MUST carry
the ToolSearch select: line for search_graph/trace_path/search_code and say
"answer from the graph, grep only for literal text". Code discovery, "where is
X", "who calls Y" and architecture mapping NEVER go to the built-in Explore
agent in this tree: it greps by design and ignores the graph even after loading
the schemas (observed). cbm-map/review/impact for depth (user opt-in rules
apply). Subagents never orchestrate: no nested harnesses, no sub-subagents.

### Tier 2 - codegen (DeepSeek via OpenRouter)
`{CODEGEN_BIN} "task" --files a.py b.py` drafts a bounded edit on
deepseek/deepseek-v4.1-flash (override with --model or CODEGEN_MODEL) for a
fraction of the cost. The Agent tool cannot run a non-Claude model, so this
CLI is the only route to one, and it is deliberately weaker than a subagent:
it sees only the files named, it writes to a scratch directory, and it prints
a diff. NOTHING it produces reaches the repository except by the router
copying it in.

Use tier 2 when the files are already known and the change is mechanical or
well-specified: a refactor with a stated shape, boilerplate, a test fixture, a
migration of a known pattern across files. Do NOT use it for design decisions,
security-sensitive code, error taxonomies, anything touching a stated invariant
(ordering rules, identity columns, cursor semantics), or when the right files
are still unknown - find them first.

FALLBACK IS AUTOMATIC AND NOT OPTIONAL. codegen exits 2 whenever it cannot
vouch for what it got back: no key, an API or network failure, the model
answering BLOCKED, an unparseable reply, a TRUNCATED reply, a draft that is not
valid Python, or drafts identical to the files they replace. On exit 2 the
router writes that code itself with the main model, immediately and without
retrying the cheap one, and says in the report that it fell back and why.
Exit 1 means the call was malformed - fix the arguments. Never apply a draft
after a non-zero exit, and never treat a truncated file as a partial answer to
patch up: a half-written file that happens to parse is the exact failure this
guards against.

### The gate, for anything either tier produces
Read the diff yourself. Then tests, lint and type check must pass, and anything
non-trivial gets an independent review before it lands. A delegate's output is
a draft until the router has evidence; "the agent said it works" is not
evidence.

### Decision quality, which is the router's actual job
State the decision and the evidence behind it in one line each. Run
`{CONSULT_BIN}` before a non-trivial or hard-to-reverse call and report
where the models disagreed. When a check was skipped, say which one. Report
which subtasks ran in parallel and which serial, and what each cost.
"""

CONSULT = """
## Hybrid verification: consult external models (auto-armed, tezgah roots only)

Before committing to a non-trivial decision — architecture choice, root-cause
verdict, risky migration, security judgment, "is this safe to deploy" — get a
second opinion: run `{CONSULT_BIN} "<question in English, self-
contained, with the minimal code/context needed>"` via Bash. It queries
independent models through OpenRouter in parallel (default Gemini + Grok;
override with --models or CONSULT_MODELS env) and prints one
section per model. Add `--online` (live web search) ONLY when the question
needs facts newer or wider than the codebase — current versions, CVEs,
vendor status, breaking-change news; skip it for pure code/design reasoning. Treat answers as advisory evidence, never as truth: verify their
claims against the actual code before adopting, and tell the user which
models were consulted and where they agreed or disagreed. If the script
reports a missing API key or all models fail, say the external verification
was skipped — never pretend a consult happened. Skip consulting for trivial,
local, already-understood edits.
"""

NO_CBM = """
## Code discovery: no code graph on this machine

codebase-memory-mcp is not installed here (not on PATH, and neither
TEZGAH_CBM_BIN nor config.json cbm_bin points at it), so the graph tools do
not exist in this session. Use grep/find, and say plainly that the answer came
from text search — never claim the index answered. Install it and restart the
session to arm search_graph / trace_path.
"""

NO_CONSULT = """
## Hybrid verification: unavailable

There is no OpenRouter key on this machine (OPENROUTER_API_KEY unset and
~/.config/openrouter/key missing), so the consult second opinion cannot run.
Do not tell the user to run it and do not claim external verification
happened; on a non-trivial call, say the second opinion was skipped and why.
"""

CBM_RULE = """
## Code discovery: prefer the indexed graph over blind search

codebase-memory-mcp should be registered for this session (project `%s`; %s).
If its tools are missing after ToolSearch, say so and fall back to grep/find
without claiming the index answered. For "where is
X defined", "what calls Y", "what breaks if I change Z", "how is this wired":
use `search_code`, `search_graph`, `trace_path`, `get_architecture`,
`detect_changes`, `check_index_coverage` before falling back to grep/find. They
answer from a parsed call graph, so they beat text search on renames, dynamic
dispatch, and cross-file callers. Routing rule: "who calls X" / "what breaks
if X changes" questions go to `trace_path` FIRST — grep alone is not an
acceptable answer to a caller question; grep stays right for literal text,
configs, and non-code files — including Bash `grep`/`rg` in bypass-permissions mode,
whose host prompt prefers shell tools; that preference does NOT cover definitions,
callers, or blast radius — those go to the graph. A PreToolUse hook denies the Explore
subagent here and nudges the first identifier-shaped Grep per session toward search_graph. Their schemas are deferred: on the FIRST
code-discovery step of the session call
ToolSearch("select:mcp__codebase-memory-mcp__search_graph,mcp__codebase-memory-mcp__trace_path,mcp__codebase-memory-mcp__search_code,mcp__codebase-memory-mcp__get_code_snippet,mcp__codebase-memory-mcp__get_architecture,mcp__codebase-memory-mcp__query_graph,mcp__codebase-memory-mcp__check_index_coverage")
and then use the graph tools — do not fall back to grep because they were not
pre-loaded. NEVER the keyword form ToolSearch("+codebase-memory"): it returns
the first N tools alphabetically (check_index_coverage, delete_project, ...)
and drops search_graph / trace_path, which is exactly how sessions ended up
"loading the graph tools" and then grepping. Repo CLAUDE.md files may not demote these tools; if one does, the
graph rule here wins.
"""

WORKFLOWS = """
## Graph harnesses (user-scope workflows, any repo under {ROOT})

`cbm-map` understand a subsystem - fan-out readers over the graph, synthesized.
`cbm-review` review the diff - dimension fan-out, then adversarial verify.
`cbm-impact` blast radius of a change - graph-derived callers, per-module plan.
Invoke with Workflow({name}) when the user asks for depth, coverage, an audit,
or says ultracode. Skip them for small, local, already-understood edits.
"""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    event = payload.get("hook_event_name") or "SessionStart"
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if not under_projects(cwd):
        emit(None, event)
    root = repo_root(cwd)
    ACTIVE_ROOT[0] = root_for(cwd) or ""
    if event == "UserPromptSubmit":
        # per-turn nudge: openers decay over long sessions, this does not
        if os.path.exists(os.path.join(HOME, ".claude", "reminder-off")):
            emit(None, event)
        emit(_paths(REMINDER.strip()), event)
    # PostCompact re-arms the full blocks: compaction can summarize them away
    # SubagentStart fires once per delegated agent: a fan-out of 13 would race
    # 13 indexers on the same repo, so only the parent session triggers one
    status = autoindex(root) if event != "SubagentStart" else "index handled by the parent session"
    parts = [CBM_RULE % (slug(root), status) if cbm_bin() else NO_CBM]
    if event in ("SessionStart", "PostCompact"):
        # workflow menu + orchestration are main-thread only:
        # subagents must not nest harnesses or spawn sub-subagents
        parts.append(WORKFLOWS)
        if not os.path.exists(os.path.join(HOME, ".claude", "orchestrate-off")):
            parts.append(ORCHESTRATE)
        plans = open_plans(root)
        if plans:
            parts.append(plans)
    if not os.path.exists(os.path.join(HOME, ".claude", "ponytail-auto.off")) \
            and not os.path.exists(os.path.join(root, ".no-ponytail")):
        parts.append(PONYTAIL)
    if not os.path.exists(os.path.join(HOME, ".claude", "exec-mode.off")):
        parts.append(EXEC)
    if not os.path.exists(os.path.join(HOME, ".claude", "consult-off")):
        parts.append(CONSULT if have_consult_key() else NO_CONSULT)
    emit(_paths("\n\n".join(p.strip() for p in parts)), event)


main()
