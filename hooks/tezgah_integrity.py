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
host PostToolUse hooks and read by the PreToolUse gate and the Stop hook.
Stdlib only. Every reader fails open so a missing or broken ledger can never
wedge a session.
"""
import json
import os
import re
import time

from tezgah_paths import cache_dir

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
# a pre-commit / husky escape hatch that skips the hooks entirely
SKIP_ENV = re.compile(r"\b(?:SKIP|HUSKY_SKIP_HOOKS)\s*=|\bHUSKY=0\b")
NO_VERIFY = re.compile(r"--no-verify\b")
GITISH = re.compile(r"\b(?:git|commit|push|husky|pre-commit|npm|yarn|pnpm)\b", re.I)
# tests disabled so a failure disappears; checked only when newly introduced
SKIP_TEST = re.compile(
    r"@pytest\.mark\.(?:skip|skipif|xfail)|@pytest\.mark\.only|"
    r"@unittest\.(?:skip|skipIf|expectedFailure)|@Ignore\b|@Disabled\b|"
    r"\bpytest\.skip\(|\bunittest\.skip\w*\(|\bt\.Skip\w*\(|"
    r"\b(?:it|test|describe)\.(?:skip|only)\(|\bxit\(|\bxdescribe\(|"
    r"\bpytestmark\s*=\s*pytest\.mark\.skip", re.I)
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


def _slug(session_id):
    return re.sub(r"[^A-Za-z0-9]+", "-", str(session_id or "nosession")).strip("-")


def _path(session_id):
    return os.path.join(cache_dir(), "evidence", _slug(session_id) + ".jsonl")


def note(session_id, kind, detail=""):
    """Append one evidence event. Best effort: a write failure is not fatal."""
    if not session_id or not kind:
        return
    try:
        d = os.path.join(cache_dir(), "evidence")
        os.makedirs(d, exist_ok=True)
        with open(_path(session_id), "a") as fh:
            fh.write(json.dumps({"kind": kind, "ts": int(time.time()),
                                 "detail": str(detail)[:200]}) + "\n")
    except OSError:
        pass


def kinds(session_id):
    """The distinct evidence kinds recorded for this session."""
    out = set()
    try:
        with open(_path(session_id)) as fh:
            for line in fh:
                try:
                    out.add(json.loads(line)["kind"])
                except (ValueError, KeyError, TypeError):
                    pass
    except OSError:
        pass
    return out


def verify_command(cmd):
    """The name of the check this command runs, or None."""
    m = VERIFY.search(str(cmd or ""))
    return m.group(0).strip() if m else None


def shortcut_command(cmd):
    """A deny reason when the command neuters verification, else None."""
    c = str(cmd or "")
    if NO_VERIFY.search(c) and GITISH.search(c):
        return ("Verification bypass denied: `--no-verify` skips the commit/push "
                "hooks that run the checks. Run the checks, fix what they report, "
                "and commit without it. A skipped hook is not a passing check.")
    if SKIP_ENV.search(c):
        return ("Verification bypass denied: an env var that skips the hooks "
                "(SKIP=/HUSKY_SKIP_HOOKS/HUSKY=0) turns the checks off. Run them "
                "instead of disabling them.")
    if verify_command(c) and NEUTER.search(c):
        return ("Verification neutered: this check is chained with `|| true` / "
                "`; true`, so it reports success no matter what it found. Run it "
                "plain and read the real exit status before claiming it passed.")
    return None


def _added(new, old):
    """The skip markers `new` introduces that `old` did not already carry."""
    if not new:
        return []
    before = set(m.group(0).lower() for m in SKIP_TEST.finditer(old or ""))
    return [m.group(0) for m in SKIP_TEST.finditer(new)
            if m.group(0).lower() not in before]


def shortcut_edit(inp):
    """A deny reason when an edit/Write adds a test-skip marker, else None.

    Only a marker that is newly introduced counts; a skip already in the file is
    not this call's doing. Reads the file from disk for a Write so the existing
    content is the baseline."""
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
    path = inp.get("file_path") or inp.get("filePath") or inp.get("path") or ""
    if old == "" and path and not inp.get("old_string"):
        try:
            with open(path) as fh:
                old = fh.read()
        except OSError:
            old = ""
    added = _added(new, old)
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


def note_tool(session_id, tool, inp, failed=False):
    """Record the evidence kind for one tool call (host PostToolUse hooks)."""
    inp = inp or {}
    kind = classify(tool, inp)
    if kind == "verify":
        kind = "verify_fail" if failed else "verify_ok"
    if kind:
        note(session_id, kind,
             inp.get("command") or inp.get("file_path")
             or inp.get("filePath") or "")


def claims(text):
    """(claims_completion, claims_verification) for a final reply."""
    t = str(text or "")
    return (bool(DONE.search(t)), bool(VERIFIED.search(t)))


def stop_reason(text, session_id, edited_hint=None):
    """Why this turn must not end yet, or None. Used by the Claude Stop hook.

    Blocks only on evidence that is checkable: a placating opener, or a
    completion/verification claim in a session that changed code (or ran
    commands) but never produced a successful check. An explicit 'doğrulanmadı'
    clears it, so honest uncertainty is always allowed."""
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
    ev = kinds(session_id)
    if edited_hint:
        ev = ev | set(edited_hint)
    if "verify_ok" in ev:
        return None
    worked = ev & {"edit", "verify", "verify_fail", "run"}
    if not worked:
        return None
    if "verify_fail" in ev:
        return ("A check failed in this session and the reply claims success. "
                "Report the failure with its exact error line, or fix it and "
                "re-run; do not describe a failed check as passing.")
    return ("This turn claims done/tested/passing but no check ran successfully "
            "in this session (nothing recorded as verify_ok). Run the real check "
            "and report its output, or mark the claim \"doğrulanmadı\". Do not "
            "describe a check you did not run as if it ran.")
