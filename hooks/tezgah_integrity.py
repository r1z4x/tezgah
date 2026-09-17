#!/usr/bin/env python3
"""Evidence ledger plus the mechanical anti-shortcut / anti-false-claim checks.

Asking a model to be honest does not work: a sycophantic or unfaithful policy
rationalizes the skipped check in fluent prose (Turpin 2023; Sharma 2023), and
self-correction without external feedback degrades (Huang 2024). So this module
enforces the two lies that can be caught from the *tool calls*, not the reply:

  * a check neutered so it cannot fail - `--no-verify`, `pytest || true`, a
    skip decorator slipped into a test;
  * a "done/tested/passing" claim with nothing observed behind it - the Stop
    hook blocks the turn when the session changed code but never ran a check.

The ledger is one JSONL file per session under the tezgah cache, written by the
host PostToolUse hooks and read by the PreToolUse gate and the Stop hook. A line
keeps {kind, ts, detail} and adds what the loop guard and the trace metrics need:
`id` (the action's identity, computed by one function both writers call), `exit`,
`out_bytes`, `fail_class`, `workspace`. `step` and `ms` are NOT written - a
reader derives them from the line's index and the `ts` delta, and writing them
would buy a second file read on every tool call. Stdlib only. Every reader fails
open so a missing or broken ledger can never wedge a session.
"""
import hashlib
import json
import os
import re
import time

from tezgah_paths import cache_dir, root_for

# A command that actually checks the change, as opposed to one that merely runs.
VERIFY = re.compile(
    r"(?:^|[|;&(]\s*|\s)(?:"
    r"(?:python3?|uv run)\s+-m\s+(?:pytest|unittest|mypy|ruff|flake8|compileall)|"
    r"pytest|py\.test|"
    r"npm\s+(?:test|t\b)|npm\s+run\s+\S*(?:test|lint|typecheck|check|build|ci)|"
    r"(?:yarn|pnpm|bun)\s+(?:test|run\s+\S*(?:test|lint|build|check))|"
    r"ruff|flake8|mypy|pyright|tsc|eslint|prettier|"
    r"vitest|jest|ava|mocha|"
    r"go\s+(?:test|vet)|"
    r"cargo\s+(?:test|clippy|check|build)|"
    r"tox|nox|pre-commit|"
    r"(?:^|\s)(?:make|just)\b|"
    r"\./\S*(?:test|check|lint)\S*|"
    r"(?:\./)?(?:gradlew|mvn)\s+\S*(?:test|check)|dotnet\s+(?:test|build)|"
    r"swift\s+test|golangci-lint|shellcheck"
    r")\b", re.I)
# forms that make a failing check exit 0, the classic "I ran it and it was fine"
NEUTER = re.compile(
    r"\|\|\s*(?:true|:|exit\s+0)(?:\s|$|[|;&])|;\s*true\s*(?:$|[|;&])")
# a pre-commit / husky escape hatch that skips the hooks entirely. SKIP/HUSKY
# only mean anything to a hook runner, so the check requires the same git/hook
# context as --no-verify: a read that merely mentions SKIP= must still pass.
SKIP_ENV = re.compile(r"\b(?:SKIP|HUSKY_SKIP_HOOKS)\s*=|\bHUSKY=0\b")
NO_VERIFY = re.compile(r"--no-verify\b")
GITISH = re.compile(r"\b(?:git|commit|push|husky|pre-commit|npm|yarn|pnpm)\b", re.I)
# tests disabled so a failure disappears; checked only when newly introduced
SKIP_TEST = re.compile(
    r"@pytest\.mark\.(?:skip|skipif|xfail|only)\b|"
    r"@unittest\.(?:skip|skipIf|skipTest|expectedFailure)\b|"
    r"@Ignore\b|@Disabled\b|"
    r"\bpytest\.skip\(|\bunittest\.(?:skip|skipIf|skipTest)\(|"
    r"\bt\.Skip\w*\(|"
    r"\b(?:it|test|describe)\.(?:skip|only)\(|\bxit\(|\bxdescribe\(|"
    r"\bpytestmark\s*=\s*pytest\.mark\.skip", re.I)
# only a test file can be disabled by a skip marker; a probe script, a note or
# a fixture that quotes one is not this rule's business
TEST_PATH = re.compile(
    r"(?:^|/)(?:tests?|__tests__|spec|specs)/|"
    r"(?:^|/)(?:test_[^/]*|conftest|[^/]*_test)\.[A-Za-z0-9]+$|"
    r"\.(?:test|spec)\.[A-Za-z0-9]+$", re.I)
# Strings, comments and heredoc bodies are neither commands nor test code: the
# repo's own tests quote a skip marker, and a commit message that *describes*
# `--no-verify` disables nothing. Both scans run on a copy where those regions
# are blanked - length preserved, so offsets stay usable.
LITERALS = re.compile(
    r"'''(?:.|\n)*?'''|\"\"\"(?:.|\n)*?\"\"\"|"
    r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|"
    r"/\*(?:.|\n)*?\*/|//[^\n]*|#[^\n]*")
HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
# a completion / verification claim, English and Turkish
DONE = re.compile(
    r"\b(done|complete[d]?|finished|implemented|fixed|shipped|wired up|"
    r"all tests? pass|tests? (?:are )?(?:green|passing)|build (?:passes|is green)|"
    r"yaptım|tamamladım|tamamlandı|bitirdim|ekledim|düzelttim|hallettim|"
    r"tüm testler geçti|testler geçti|testler yeşil|çalışıyor)\b", re.I)
VERIFIED = re.compile(
    r"\b(tested|verified|i ran|ran the (?:tests?|suite|build|lint|checks?)|"
    r"doğruladım|test ettim|kontrol ettim|denetledim|doğrulandı|test edildi)\b",
    re.I)
# an explicit admission that removes the lie: an unverified claim is allowed
NEGATED = re.compile(
    r"doğrulanmadı|doğrulamadım|unverified|not verified|could ?n[o']t verify|"
    r"verification (?:was )?skipped|kontrol edilmedi|test edilmedi", re.I)
# a reply must not OPEN by placating; checked only at the very start
SYCOPHANT = re.compile(
    r"^\s*(?:(?:evet|yes|ah|oh|hmm)[,!\s]+)?"
    r"(?:haklısın|haklısınız|you'?re (?:absolutely )?right|you are right|"
    r"absolutely right|good catch|great catch|iyi yakaladın|"
    r"detaylı bakmadım|i didn'?t look closely|i should have checked|"
    r"my mistake|my bad|sorry, i)", re.I)

WRITE_TOOLS = ("edit", "write", "multiedit", "notebookedit", "apply_patch",
               "str_replace_editor", "create_file", "str_replace", "edit_file",
               "write_file", "search_replace")
BASH_TOOLS = ("bash", "shell", "command", "exec_command", "run_command",
              "powershell")


# The host's error text, classified so the loop guard can tell a retry that may
# work from one that cannot: a timeout or a rate limit is worth one more attempt,
# a bad flag or a missing file is not. The hosts that report an error report it
# as prose, not as a code, so the class comes from the text.
TRANSIENT_ERROR = re.compile(
    r"timed? ?out|timeout|deadline exceeded|connection (?:reset|refused|aborted)|"
    r"temporarily unavailable|rate ?limit|\b(?:429|502|503|504|529)\b|"
    r"ECONNRESET|ETIMEDOUT|EPIPE|EAGAIN|broken pipe|try again|please retry|"
    r"overloaded|network", re.I)
PERMANENT_ERROR = re.compile(
    r"command not found|no such file|not found|cannot find|permission denied|"
    r"unrecognized|unknown option|invalid|syntax error|does not exist|"
    r"ModuleNotFoundError|ImportError|assertion|expected|"
    r"\b(?:126|127|401|403|404|422)\b", re.I)
# the fields the ledger contract adds to {kind, ts, detail}. Every reader treats
# a missing key as None, so a writer leaves out what it did not know rather than
# writing nulls into the file it reads back on every gated call.
LEDGER_FIELDS = frozenset(("id", "exit", "out_bytes", "fail_class", "workspace"))


def fail_class(error):
    """How the host's error text classifies: "transient", "permanent",
    "unknown", or None when the host reported no error at all.

    The loop guard spends a retry on a transient class and none on a permanent
    one, so the two have to be told apart from the text alone."""
    text = str(error or "").strip()
    if not text:
        return None
    if TRANSIENT_ERROR.search(text):
        return "transient"
    if PERMANENT_ERROR.search(text):
        return "permanent"
    return "unknown"


def call_id(tool, inp):
    """The action identity: sha1(tool.lower() + " " + canonical(args))[:12], or
    None when the args cannot be canonicalized.

    The PreToolUse gate and the PostToolUse hook both compute it here, so they
    agree on which call a ledger row belongs to. A shell line is canonicalized
    to its whitespace-collapsed text: the digest has to be reproducible in every
    writer (opencode's half is a JS port), and a programs-only digest would give
    every `git ...` call one id - the loop guard would then deny a retry the
    agent had already fixed. Any other tool's args are the compact sorted-key
    JSON of its input, so key order and spacing cannot fork one action in two."""
    name = str(tool or "").lower()
    if name in BASH_TOOLS:
        args = " ".join(str((inp or {}).get("command")
                            or (inp or {}).get("cmd") or "").split())
    else:
        try:
            args = json.dumps(inp or {}, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False)
        except (TypeError, ValueError):
            return None
    return hashlib.sha1(("%s %s" % (name, args)).encode("utf-8", "replace")
                        ).hexdigest()[:12]


def _slug(session_id):
    return re.sub(r"[^A-Za-z0-9]+", "-", str(session_id or "nosession")).strip("-")


def _path(session_id):
    return os.path.join(cache_dir(), "evidence", _slug(session_id) + ".jsonl")


def note(session_id, kind, detail="", **fields):
    """Append one evidence event. Best effort: a write failure is not fatal.

    The extra keys are the ledger contract's (`id`, `exit`, `out_bytes`,
    `fail_class`, `workspace`); a caller's typo is dropped rather than parked in
    the file, and a None value is left out because every reader treats a missing
    key as None - a line should carry what its writer actually knew."""
    if not session_id or not kind:
        return
    row = {"kind": kind, "ts": int(time.time()), "detail": str(detail)[:200]}
    row.update({k: v for k, v in fields.items()
                if v is not None and k in LEDGER_FIELDS})
    try:
        d = os.path.join(cache_dir(), "evidence")
        os.makedirs(d, exist_ok=True)
        with open(_path(session_id), "a") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def kinds(session_id):
    """The distinct evidence kinds recorded for this session."""
    return {str(e.get("kind")) for e in events(session_id) if e.get("kind")}


# How much of the file one backwards read pulls in. The tail is a bounded number
# of lines, so a chunk size only decides how many read() calls it takes.
TAIL_CHUNK = 8192


def _tail_lines(path, n):
    """The last `n` lines of a file, read by seeking from the end.

    An unreadable file yields nothing: this is the reader the PreToolUse path
    uses, and a gate that cannot see the ledger must let the call through."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            data = b""
            while pos > 0 and data.count(b"\n") <= n:
                step = min(TAIL_CHUNK, pos)
                pos -= step
                fh.seek(pos)
                data = fh.read(step) + data
    except OSError:
        return []
    return [line.decode("utf-8", "replace") for line in data.splitlines()[-n:]]


def _parse(lines):
    """The parseable JSON objects among `lines`, oldest first. A line a lock or
    a killed process left half-written is skipped, never fatal: the gate reads
    this on every gated call."""
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def events(session_id, tail=None):
    """Every parseable ledger entry for this session, oldest first.

    With `tail`, only the last `tail` lines are read. The file grows with the
    session and the gate reads it on every gated call, so the tail path must
    never parse the whole of it."""
    if tail:
        return _parse(_tail_lines(_path(session_id), tail))
    try:
        with open(_path(session_id)) as fh:
            return _parse(fh)
    except OSError:
        return []


def prior_calls(session_id, digest, tail=200):
    """(attempts already made, the newest attempt's exit, its fail_class) for
    this action identity, over the ledger tail only.

    The loop guard's ceiling depends on whether the last failure was transient,
    so the class travels with the count: reading the file a second time for it
    would double the only file I/O the PreToolUse path may do."""
    rows = [e for e in events(session_id, tail=tail) if e.get("id") == digest]
    if not rows:
        return 0, None, None
    return len(rows), rows[-1].get("exit"), rows[-1].get("fail_class")


# Appended to a non-verify event's detail when the host reported its outcome, so
# a failed run is countable without a new kind (kinds are pinned by tests and by
# the Stop rule, detail is free text nothing parses).
FAILED_MARK = "[exit!=0]"


def counters(session_id):
    """One session's ledger, aggregated: what the gate refused, what ran, what
    failed, which cheap-model tier was used, and the trace metrics.

    This is the instrumentation the contract's own mechanisms need before
    anyone can claim they help: a rule that never fires is indistinguishable
    from a rule that is wrong. `tool_error_rate` is over the rows whose outcome
    the host actually reported (exit 0 or 1) - a host that reports none would
    otherwise read as a perfect success rate - and `false_completion` counts the
    claim rows a stop refused, so the rate is false_completion / claims."""
    out = {"events": 0, "denies": {}, "nudges": 0, "kinds": {},
           "consult": 0, "codegen": 0, "codegen_failed": 0, "fanout": 0,
           "steps": 0, "tool_error_rate": None, "claims": 0,
           "false_completion": 0}
    decided = errors = 0
    for entry in events(session_id):
        out["events"] += 1
        kind = str(entry.get("kind") or "")
        detail = str(entry.get("detail") or "")
        out["kinds"][kind] = out["kinds"].get(kind, 0) + 1
        if entry.get("exit") in (0, 1):
            decided += 1
            if entry.get("exit") == 1:
                errors += 1
        if kind == "deny":
            rule = detail.split(":", 1)[0].strip() or "other"
            out["denies"][rule] = out["denies"].get(rule, 0) + 1
        elif kind == "nudge":
            out["nudges"] += 1
        elif kind == "claim":
            out["claims"] += 1
            if detail.startswith("blocked"):
                out["false_completion"] += 1
        if "consult" in detail:
            out["consult"] += 1
        if "codegen" in detail:
            out["codegen"] += 1
            if detail.endswith(FAILED_MARK):
                out["codegen_failed"] += 1
    out["steps"] = out["events"]
    if decided:
        out["tool_error_rate"] = round(errors / decided, 4)
    out["fanout"] = sum(out["kinds"].get(k, 0)
                        for k in ("orch", "task", "agent", "subagent"))
    return out


def verify_command(cmd):
    """The name of the check this command runs, or None."""
    m = VERIFY.search(str(cmd or ""))
    return m.group(0).strip() if m else None


def _blank_heredocs(text):
    """`text` with every heredoc body blanked.

    An unterminated heredoc is left visible, so a bypass cannot hide behind a
    missing terminator. ponytail: a payload handed to a shell through a heredoc
    reads as data here, so a bypass written that way is not caught - telling
    those apart needs a real shell parser."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        m = HEREDOC.search(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        tag = m.group(1)
        j = i + 1
        while j < len(lines) and lines[j].strip() != tag:
            j += 1
        if j == len(lines):  # unterminated: keep it visible
            out.append(lines[i])
            i += 1
            continue
        out.append(lines[i])
        out.extend(" " * len(line) for line in lines[i + 1:j])
        out.append(lines[j])
        i = j + 1
    return "\n".join(out)


def mask(text):
    """The text with quoted strings, comments and heredoc bodies blanked."""
    return LITERALS.sub(lambda m: " " * len(m.group(0)),
                        _blank_heredocs(str(text or "")))


def shortcut_command(cmd):
    """A deny reason when the command neuters verification, else None.

    The scan runs on the masked text, so a commit message that names
    `--no-verify` (quoted, or a heredoc body) is not a bypass - the flag has to
    survive in command position, next to a git/hook command."""
    c = mask(cmd)
    if NO_VERIFY.search(c) and GITISH.search(c):
        return ("Verification bypass denied: `--no-verify` skips the commit/push "
                "hooks that run the checks. Run the checks, fix what they report, "
                "and commit without it. A skipped hook is not a passing check.")
    if SKIP_ENV.search(c) and GITISH.search(c):
        return ("Verification bypass denied: an env var that skips the hooks "
                "(SKIP=/HUSKY_SKIP_HOOKS/HUSKY=0) turns the checks off. Run them "
                "instead of disabling them.")
    if verify_command(c) and NEUTER.search(c):
        return ("Verification neutered: this check is chained with `|| true` / "
                "`; true`, so it reports success no matter what it found. Run it "
                "plain and read the real exit status before claiming it passed.")
    return None


def _added(new, old):
    """The skip markers `new` introduces that `old` did not already carry.

    Counted per marker kind on the masked text, so rewriting a skip in place
    stays legal, one more skip does not, and a marker inside a string (a test
    that is *about* the rule) is not a disable."""
    if not new:
        return []
    before = {}
    for m in SKIP_TEST.finditer(old or ""):
        before[m.group(0).lower()] = before.get(m.group(0).lower(), 0) + 1
    out = []
    for m in SKIP_TEST.finditer(new):
        name = m.group(0)
        low = name.lower()
        if before.get(low, 0) > 0:
            before[low] -= 1
        elif name not in out:
            out.append(name)
    return out


def shortcut_edit(inp):
    """A deny reason when an edit/Write adds a test-skip marker, else None.

    Three gates keep it on the contract's target - a test disabled so a failure
    disappears: the write has to be a test file, the marker has to be outside
    strings and comments, and it has to be newly introduced (a skip already in
    the file is not this call's doing). Reads the file from disk for a Write so
    the existing content is the baseline."""
    old = str(inp.get("old_string") or inp.get("oldString") or "")
    new = str(inp.get("new_string") or inp.get("newString")
              or inp.get("content") or "")
    if not new:
        edits = inp.get("edits")
        if isinstance(edits, list):
            old = " ".join(str(e.get("old_string", "")) for e in edits
                           if isinstance(e, dict))
            new = " ".join(str(e.get("new_string", "")) for e in edits
                           if isinstance(e, dict))
    path = str(inp.get("file_path") or inp.get("filePath")
               or inp.get("path") or "")
    if not TEST_PATH.search(path):
        return None
    if old == "" and path and not inp.get("old_string"):
        try:
            with open(path) as fh:
                old = fh.read()
        except OSError:
            old = ""
    added = _added(mask(new), mask(old))
    if added:
        return ("Test disable denied: this change adds %s. Making a failing test "
                "disappear is not a fix - fix the code or say the test is failing. "
                "If the skip is genuinely intended, ask the user first."
                % ", ".join(sorted(set(added))))
    return None


def classify(tool, inp):
    """The evidence kind for a tool call, or None. Shared by the host hooks."""
    t = str(tool or "").lower()
    if t in WRITE_TOOLS:
        return "edit"
    if t in BASH_TOOLS:
        cmd = inp.get("command") or inp.get("cmd") or ""
        return "verify" if verify_command(cmd) else "run"
    return None


def note_tool(session_id, tool, inp, failed=False, out_bytes=None, error=None,
              cwd=None):
    """Record the evidence kind for one tool call (host PostToolUse hooks).

    `failed=None` means the host reported no outcome: the call is recorded as a
    check that RAN (`verify`), never as one that passed - a ledger that says
    verify_ok for a check nobody saw succeed is the lie it exists to catch. The
    same holds for a check run through a pipe: the status belongs to the pipe's
    last stage, so `pytest | tail` records as a check that ran, whatever the
    host reported for the line."""
    inp = inp or {}
    cmd = str(inp.get("command") or inp.get("cmd") or "")
    kind = classify(tool, inp)
    if kind == "verify":
        if failed is None or "|" in cmd:
            kind = "verify"
        else:
            kind = "verify_fail" if failed else "verify_ok"
    if kind:
        detail = (cmd or inp.get("file_path") or inp.get("filePath") or "")
        if failed:
            detail = "%s %s" % (detail, FAILED_MARK)
        note(session_id, kind, detail,
             id=call_id(tool, inp),
             exit=None if failed is None else int(bool(failed)),
             out_bytes=out_bytes,
             fail_class=fail_class(error),
             workspace=root_for(cwd) if cwd else None)


def claims(text):
    """(claims_completion, claims_verification) for a final reply."""
    t = str(text or "")
    return (bool(DONE.search(t)), bool(VERIFIED.search(t)))


def passing_check(entry):
    """True when this ledger row is evidence that a check passed.

    A `verify_ok` is support only when the host reported exit 0, the tool
    returned something (an exit-0-but-empty result is the classic silent
    failure) and the command was not piped - a pipe's status belongs to its last
    stage, so `pytest | tail` proves nothing about pytest. Everything else is a
    check that ran with an outcome nobody saw."""
    if entry.get("kind") != "verify_ok":
        return False
    if "exit" not in entry:
        # ponytail: rows written before plan 012 carry no `exit`. Reading them as
        # unsupported would block an open session on its own history the moment
        # this rule lands - a false positive on the user, which is worse than the
        # hole it closes for one release. Tolerated until the ledger turns over;
        # drop this branch when no live session's first row predates plan 012.
        return "[exit!=0]" not in str(entry.get("detail") or "")
    if entry.get("exit") != 0 or entry.get("out_bytes") == 0:
        return False
    return "|" not in str(entry.get("detail") or "")


def _last_verify(rows):
    """`last_verify`'s fold, over rows already read."""
    state = None
    for entry in rows:
        kind = entry.get("kind")
        if kind == "verify_ok":
            state = "ok" if passing_check(entry) else "ran"
        elif kind == "verify_fail":
            state = "fail"
        elif kind == "verify":
            state = "ran"
    return state


def last_verify(session_id):
    """The newest verification state the ledger holds: "ok", "fail", "ran" (the
    host reported no exit status, or reported one this reader does not accept as
    proof) or None when no check ran.

    `kinds()` is a set, so it cannot tell a failure that came *after* a success
    from one that came before it; the Stop rule needs the order."""
    return _last_verify(events(session_id))


def stop_reason(text, session_id, edited_hint=None):
    """Why this turn must not end yet, or None. Used by the Stop hooks (Claude,
    Codex, omp and Cursor, which share the payload fields and the block envelope).

    The verdict is recorded either way, as a `claim` row: a blocked stop leaves
    no trace otherwise, and the false-completion rate (counters) needs both the
    refusals and the claims that were allowed through."""
    reason = _stop_block(text, session_id, edited_hint)
    if reason:
        note(session_id, "claim", "blocked: %s" % str(reason)[:80])
    elif any(claims(text)):
        note(session_id, "claim", "ok")
    return reason


def _stop_block(text, session_id, edited_hint=None):
    """stop_reason's decision, without the ledger side effect.

    Blocks only on evidence that is checkable: a placating opener, or a
    completion/verification claim whose newest check did not pass. An explicit
    'doğrulanmadı' clears it, so honest uncertainty is always allowed."""
    t = str(text or "")
    if SYCOPHANT.search(t):
        return ("Reply opens with placation, which the tezgah contract bans. "
                "State the fact and the fix in one plain sentence - never "
                "\"haklısın\" / \"you're right\" / \"detaylı bakmadım\" / an "
                "apology. If the user is right, fix it; if wrong, show the "
                "evidence.")
    done, verified = claims(t)
    if not (done or verified) or NEGATED.search(t):
        return None
    rows = events(session_id)
    ev = {str(entry.get("kind")) for entry in rows}
    if edited_hint:
        ev = ev | set(edited_hint)
    # the newest check decides: "the tests pass" is false when a later run
    # failed, even though an earlier one succeeded
    if _last_verify(rows) == "fail":
        return ("A check failed in this session and the reply claims success. "
                "Report the failure with its exact error line, or fix it and "
                "re-run; do not describe a failed check as passing.")
    if any(passing_check(entry) for entry in rows):
        return None
    worked = ev & {"edit", "verify", "verify_fail", "run"}
    if not worked:
        return None
    return ("This turn claims done/tested/passing but no check ran successfully "
            "in this session (nothing recorded as verify_ok with a real result "
            "and an unmasked command). Run the real check and report its output, "
            "or mark the claim \"doğrulanmadı\". Do not describe a check you did "
            "not run as if it ran.")
