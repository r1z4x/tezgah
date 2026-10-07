#!/usr/bin/env python3
"""Run the tests a change actually touches, in parallel, not the whole suite.

    python3 tests/impacted.py --run hooks/tezgah_integrity.py bin/tezgah-task
    python3 tests/impacted.py --ref main          # changed since main
    python3 tests/impacted.py --list hooks/...    # print the set, run nothing
    python3 tests/impacted.py --all               # the full suite, sharded

Changed paths map to test modules (tests/test_<name>.py) by five rules, in order:

  1. the owner: `hooks/tezgah_X.py` -> `test_X.py` when that module exists.
  2. importers: any test module whose source (or a `tests/_probe_*.py` helper)
     names `tezgah_X`.
  3. entry points: `bin/<prog>`, `hooks/projects-*.py`, `statusline.py`,
     `skills/<skill>/**` map to every test module whose source names that path
     or its basename.
  4. `OVERRIDES` below: the hand-known edges the static scan cannot see, e.g.
     `tezgah_integrity`/`tezgah_gate` are also exercised through the codex,
     cursor and dsh hook tests and through the opencode plugin.
  5. any other path (`hosts/**`, `packaging/**`, config files): the modules
     that name the path itself, its `os.path.join` spelling or the
     tests/support.py constant built from it - never its basename alone.

`tests/support.py`, `tests/_probe_*.py` and any path no rule maps are the fail
safe: the FULL suite runs. A docs-only change maps to the docs modules only.
Every module runs as `python3 -m unittest discover -s tests -p <module>` in its
own process with an isolated HOME and TMPDIR, so the ledger never writes to the
real cache and each row still carries `python3 -m unittest` as the check. A new
hooks module with no mapping is pinned by `tests/test_impacted.py`.

With `--all` nothing is mapped: every module runs, sharded across the pool
(measured 2026-10-01: 8 shards, 103.5 s wall, against 566.9 s serial; plan 043
re-measured 199.1 s wall for the grown suite).

A run that executes no module - nothing maps, or `--ref` finds no change -
exits 5, unittest's own "no tests ran" code, so it never reads as a pass.
"""
import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
TESTS = os.path.join(REPO, "tests")

# hand-known edges the static scan cannot see
OVERRIDES = {
    "tezgah_integrity": ("codex_hook", "cursor_hook", "opencode_plugin",
                         "dsh_hooks", "gate"),
    "tezgah_gate": ("codex_hook", "cursor_hook", "opencode_plugin",
                    "dsh_hooks", "integrity", "taste"),
    "tezgah_lang": ("gate",),
    "tezgah_policy": ("skills", "context", "setup"),
    "tezgah_paths": None,  # None means FULL: every module imports the paths
    "tezgah_context": ("gate", "skills", "agents", "taste"),
    # the lessons block and the docs fallback rank through it
    "tezgah_rank": ("context", "docs_router", "embed"),
    # the opt-in fusion both of those call, and the registry rows that probe it
    "tezgah_embed": ("context", "docs_router", "apps_registry"),
    # the opt-in taste capture the prompt path, note_tool and the snapshot store
    # call, and the write note every host's post-tool channel carries
    "tezgah_taste": ("context", "integrity", "snapshot", "opencode_plugin",
                     "taste_ledger", "codex_hook", "cursor_hook", "omp_hook",
                     "dsh_hooks"),
    # the taste ledger the session block, the write note and the CLI read
    "tezgah_taste_ledger": ("taste", "taste_cli", "context"),
    # the SQLite store: the taste tables and the evidence ledger every hook
    # writes and reads, so FULL
    "tezgah_store": None,
}
# a change only in these maps to only these modules
DOC_TARGETS = ("test_docs.py", "test_docs_router.py", "test_clarity.py")
ENTRY_PREFIXES = ("bin/", "hooks/", "hosts/", "statusline.py", "skills/")


def test_modules():
    return sorted(f for f in os.listdir(TESTS)
                  if f.startswith("test_") and f.endswith(".py"))


def module_stem(module):
    return module[len("test_"):-len(".py")]


def _tests_mentioning(needle, cache):
    hits = []
    for module in test_modules():
        src = cache.setdefault(module, _read(os.path.join(TESTS, module)))
        if (needle.search(src) if hasattr(needle, "search") else needle in src):
            hits.append(module)
    return hits


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _helper_importers(stem, cache):
    """The test modules that import the tests/ helper `stem`, or None (FULL).

    Only an import statement counts (`import x`, `import x as y`, `import a,
    x`, `from x import ...`). Any doubt is the fail-safe: a test module that
    names the helper without such a line, or another tests/ helper that names
    it (a transitive importer the scan would miss), runs the whole suite
    (consult review, 2026-10-03)."""
    word = re.compile(r"\b%s\b" % re.escape(stem))
    line = re.compile(r"^\s*(?:from\s+%s\s+import\b|import\s+[^\n#]*\b%s\b)"
                      % (re.escape(stem), re.escape(stem)), re.M)
    for name in os.listdir(TESTS):
        if (name.endswith(".py") and not name.startswith("test_")
                and name != stem + ".py"
                and word.search(_read(os.path.join(TESTS, name)))):
            return None
    hits = []
    for module in test_modules():
        src = cache.setdefault(module, _read(os.path.join(TESTS, module)))
        if line.search(src):
            hits.append(module)
        elif word.search(src):
            return None
    return hits or None


def modules_for(path, cache):
    """The test modules this changed path maps to, or None for the FULL suite."""
    path = os.path.relpath(path, REPO).replace(os.sep, "/")
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    if path == "tests/support.py" or path.startswith("tests/_probe_"):
        return None
    if path.startswith("tests/"):
        if ext == ".py" and name.startswith("test_"):
            return [name]
        return _helper_importers(stem, cache) if ext == ".py" else None
    # docs-only changes exercise the docs modules alone
    if path.startswith("docs/") or path in ("docs/index.json",):
        mods = [m for m in DOC_TARGETS if os.path.exists(os.path.join(TESTS, m))]
        return mods or None
    if path == "CHANGELOG.md" or path == "MANIFEST":
        mods = _tests_mentioning("packaging", cache)
        return mods or None
    if os.sep not in path and path.endswith(".md"):
        # a root-level page (RELEASING.md, CONTRIBUTING.md, AGENTS.md, README.md):
        # the docs modules read the pages the index names, and the packaging tests
        # hold the shipped listing - not the whole suite
        mods = {m for m in DOC_TARGETS if os.path.exists(os.path.join(TESTS, m))}
        mods |= set(_tests_mentioning(path, cache))
        return sorted(mods) or None
    if path.startswith("skills/"):
        stem_skill = path.split("/")[1]
        mods = set(_tests_mentioning(stem_skill, cache)) | set(
            _tests_mentioning(path, cache))
        return sorted(mods) or None
    if path.startswith("hooks/tezgah_") and ext == ".py":
        mod_stem = stem[len("tezgah_"):] if stem.startswith("tezgah_") else stem
        candidates = {"test_%s.py" % s for s in (stem, mod_stem)}
        hits = {c for c in candidates if os.path.exists(os.path.join(TESTS, c))}
        hits |= set(_tests_mentioning("tezgah_" + mod_stem, cache))
        if OVERRIDES.get("tezgah_" + mod_stem, ("x",)) is None:
            return None  # fail-safe: this module is imported everywhere
        for extra in OVERRIDES.get("tezgah_" + mod_stem, ()):
            hits.add("test_%s.py" % extra)
        if not any(os.path.exists(os.path.join(TESTS, c)) for c in candidates):
            # a hooks module with no test module of its own: the mention scan is
            # not evidence enough (a test that merely names the path pulls
            # itself in), so this is the fail-safe, and the guard test in
            # tests/test_impacted.py is what keeps a new module from landing
            # here unnoticed
            return None
        return sorted(hits) or None
    if path.startswith(("hooks/", "bin/", "skills/")) or path == "statusline.py":
        hits = set(_tests_mentioning(name, cache)) | set(
            _tests_mentioning(stem, cache))
        if path.startswith("bin/tezgah-setup"):
            hits |= {"test_setup.py", "test_install_tree.py",
                     "test_mcp_features.py", "test_tezgah_mcp_wiring.py"}
        for hook_stem, extras in OVERRIDES.items():
            if hook_stem in path:
                hits |= {"test_%s.py" % e for e in extras}
        return sorted(hits) or None
    # any other path (hosts/, packaging/, config): the modules that name it
    # (`_path_needles`). Not its basename or stem: `hook.py`, `hooks.json`,
    # `tezgah.js` are in nearly every module, and that rule mapped one host
    # file to 75-85 of 90 (measured 2026-10-07). The map's own test names paths
    # as data, so it is not a hit; a path no module names is the fail-safe.
    needles = _path_needles(path)
    if path.startswith("packaging/"):
        needles.append(name)  # install.sh, build.sh: specific enough
    hits = set()
    for needle in needles:
        hits |= set(_tests_mentioning(needle, cache))
    hits.discard("test_impacted.py")
    return sorted(hits) or None


def _path_needles(path):
    """How a test module names the repo path `path`: the path itself, the
    `os.path.join` spelling of its last two parts across any line breaks
    (`"codex",\\n "hook.py"`, which also reads an installed copy of the file),
    and the tests/support.py constant built from the whole spelling
    (`CODEX_HOOK`)."""
    parts = path.split("/")
    joined = ", ".join('"%s"' % part for part in parts)
    needles = [path, re.compile(r",\s*".join('"%s"' % re.escape(part)
                                              for part in parts[-2:]))]
    for line in _read(os.path.join(TESTS, "support.py")).splitlines():
        const = re.match(r"^([A-Z_]+)\s*=\s*os\.path\.join\(REPO,\s*(.+)\)\s*$", line)
        if const and const.group(2) == joined:
            needles.append(const.group(1))
    return needles


def changed_paths(ref):
    if ref:
        out = subprocess.run(
            ["git", "-C", REPO, "diff", "--name-only", "%s...HEAD" % ref],
            capture_output=True, text=True)
        if out.returncode:
            # an unknown ref is not an empty diff: it must not read as "no change"
            raise ValueError(out.stderr.strip() or "git diff failed for %s" % ref)
        paths = out.stdout.splitlines()
    else:
        paths = []
    status = subprocess.run(["git", "-C", REPO, "status", "--porcelain"],
                            capture_output=True, text=True)
    for line in status.stdout.splitlines():
        paths.append(line[3:].strip().strip('"'))
    return [p for p in paths if p]


def resolve(paths, cache):
    """(modules, unmapped): the union of every path's set; any None means FULL."""
    mods, unmapped = set(), []
    for path in paths:
        got = modules_for(path, cache)
        if got is None:
            unmapped.append(path)
        else:
            mods |= set(got)
    return sorted(mods), unmapped


def _run_module(module, log_path):
    home = tempfile.mkdtemp(prefix="impacted-home-")
    tmp = tempfile.mkdtemp(prefix="impacted-tmp-")
    env = dict(os.environ, HOME=home, TMPDIR=tmp,
               TEZGAH_CODEGRAPH_BIN=os.path.join(home, "no-such-codegraph"),
               TEZGAH_ORX_BIN=os.path.join(home, "no-such-orx"),
               TEZGAH_CONSULT_CLIS="", TEZGAH_UPDATE_CHECK="0")
    start = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", TESTS,
         "-p", module],
        cwd=REPO, env=env, capture_output=True, text=True)
    seconds = time.time() - start
    section = ("\n===== %s (%.1fs, exit %d) =====\n%s%s\n"
               % (module, seconds, proc.returncode, proc.stdout, proc.stderr))
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(section)
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return module, proc.returncode, seconds, section


def run_pool(modules, work_dir, workers):
    log_path = os.path.join(work_dir, "impacted.log")
    open(log_path, "w").close()
    rows, failed, sections = [], [], {}
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_module, m, log_path) for m in modules]
        for fut in concurrent.futures.as_completed(futures):
            module, rc, seconds, section = fut.result()
            rows.append((module, rc, seconds))
            if rc:
                failed.append(module)
                sections[module] = section
    rows.sort()
    for module in sorted(sections):
        print(sections[module], end="")
    for module, rc, seconds in rows:
        print("  %-34s %-4s %6.1fs" % (module, "FAIL" if rc else "ok", seconds))
    print("%d module(s) in %.1fs; log: %s"
          % (len(rows), time.time() - start, log_path))
    return failed


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--run", nargs="+", metavar="PATH",
                    help="run the modules these changed paths map to")
    ap.add_argument("--ref", metavar="REF",
                    help="diff base for --run when no paths are given")
    ap.add_argument("--all", action="store_true",
                    help="run every module, sharded (the full suite)")
    ap.add_argument("--list", nargs="*", metavar="PATH",
                    help="print the mapped modules, run nothing")
    ap.add_argument("--workers", type=int,
                    default=min(8, os.cpu_count() or 2))
    args = ap.parse_args(argv)

    cache = {}
    if args.list is not None:
        if args.list:
            mods, unmapped = resolve(args.list, cache)
            print("\n".join(mods if not unmapped
                            else mods + ["FULL (unmapped: %s)" % ", ".join(unmapped)]))
        else:
            print("\n".join(test_modules()))
        return 0

    if args.all:
        modules = test_modules()
        if not modules:
            print("no test module found; nothing to run")
            return 5
    elif args.run:
        mods, unmapped = resolve(args.run, cache)
        if unmapped:
            print("unmapped paths -> FULL suite: %s" % ", ".join(unmapped),
                  file=sys.stderr)
            modules = test_modules()
        else:
            modules = mods or []
        if not modules:
            print("no test module maps to the changed paths; nothing to run")
            return 5
    elif args.ref:
        try:
            paths = changed_paths(args.ref)
        except ValueError as exc:
            print("--ref %s: %s" % (args.ref, exc), file=sys.stderr)
            return 2
        if not paths:
            print("no change since %s; nothing to run" % args.ref)
            return 5
        return main(["--run"] + paths)
    else:
        ap.print_help()
        return 2

    workers = max(1, min(args.workers, len(modules)))
    work_dir = tempfile.mkdtemp(prefix="impacted-")
    failed = run_pool(modules, work_dir, workers)
    if failed:
        print("FAILED: %s" % ", ".join(failed))
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
