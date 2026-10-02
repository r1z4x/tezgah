#!/usr/bin/env python3
"""Run the tests a change actually touches, in parallel, not the whole suite.

    python3 tests/impacted.py --run hooks/tezgah_integrity.py bin/tezgah-task
    python3 tests/impacted.py --ref main          # changed since main
    python3 tests/impacted.py --list hooks/...    # print the set, run nothing
    python3 tests/impacted.py --all               # the full suite, sharded

Changed paths map to test modules (tests/test_<name>.py) by four rules, in order:

  1. the owner: `hooks/tezgah_X.py` -> `test_X.py` when that module exists.
  2. importers: any test module whose source (or a `tests/_probe_*.py` helper)
     names `tezgah_X`.
  3. entry points: `bin/<prog>`, `hooks/projects-*.py`, `hosts/<host>/**`,
     `statusline.py`, `skills/<skill>/**` map to every test module whose source
     names that path or its basename.
  4. `OVERRIDES` below: the hand-known edges the static scan cannot see, e.g.
     `tezgah_integrity`/`tezgah_gate` are also exercised through the codex,
     cursor and dsh hook tests and through the opencode plugin.

`tests/support.py`, `tests/_probe_*.py` and any path no rule maps are the fail
safe: the FULL suite runs. A docs-only change maps to the docs modules only.
Every module runs as `python3 -m unittest discover -s tests -p <module>` in its
own process with an isolated HOME and TMPDIR, so the ledger never writes to the
real cache and each row still carries `python3 -m unittest` as the check. A new
hooks module with no mapping is pinned by `tests/test_impacted.py`.

With `--all` nothing is mapped: every module runs, sharded across the pool
(measured 2026-10-01: 8 shards, 103.5 s wall, against 566.9 s serial).
"""
import argparse
import concurrent.futures
import os
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
                    "dsh_hooks", "integrity"),
    "tezgah_lang": ("gate",),
    "tezgah_policy": ("skills", "context", "setup"),
    "tezgah_paths": None,  # None means FULL: every module imports the paths
    "tezgah_context": ("gate", "skills", "agents"),
}
# a change only in these maps to only these modules
DOC_TARGETS = ("docs", "docs_router")
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
        if needle in src:
            hits.append(module)
    return hits


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def modules_for(path, cache):
    """The test modules this changed path maps to, or None for the FULL suite."""
    path = os.path.relpath(path, REPO).replace(os.sep, "/")
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    if path == "tests/support.py" or path.startswith("tests/_probe_"):
        return None
    if path.startswith("tests/"):
        return [name] if ext == ".py" and name.startswith("test_") else None
    # docs-only changes exercise the docs modules alone
    if path.startswith("docs/") or path in ("docs/index.json",):
        mods = [m for m in DOC_TARGETS if os.path.exists(
            os.path.join(TESTS, "test_%s.py" % m))]
        return mods or None
    if path == "CHANGELOG.md" or path == "MANIFEST":
        mods = _tests_mentioning("packaging", cache)
        return mods or None
    if os.sep not in path and path.endswith(".md"):
        # a root-level page (RELEASING.md, CONTRIBUTING.md, AGENTS.md, README.md):
        # the docs modules read the pages the index names, and the packaging tests
        # hold the shipped listing - not the whole suite
        mods = {m for m in DOC_TARGETS if os.path.exists(os.path.join(TESTS, "test_%s.py" % m))}
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
    if path.startswith(("hooks/", "hosts/", "bin/", "skills/")) \
            or path == "statusline.py":
        hits = set(_tests_mentioning(name, cache)) | set(
            _tests_mentioning(stem, cache))
        if path.startswith("bin/tezgah-setup"):
            hits |= {"test_setup.py", "test_install_tree.py",
                     "test_mcp_features.py", "test_tezgah_mcp_wiring.py"}
        for hook_stem, extras in OVERRIDES.items():
            if hook_stem in path:
                hits |= {"test_%s.py" % e for e in extras}
        return sorted(hits) or None
    return None  # an unmapped path: the fail-safe


def changed_paths(ref):
    if ref:
        out = subprocess.run(
            ["git", "-C", REPO, "diff", "--name-only", "%s...HEAD" % ref],
            capture_output=True, text=True)
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
               TEZGAH_CONSULT_CLIS="")
    start = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", module],
        cwd=REPO, env=env, capture_output=True, text=True)
    seconds = time.time() - start
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("\n===== %s (%.1fs, exit %d) =====\n%s%s\n"
                 % (module, seconds, proc.returncode, proc.stdout, proc.stderr))
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return module, proc.returncode, seconds


def run_pool(modules, work_dir, workers):
    log_path = os.path.join(work_dir, "impacted.log")
    open(log_path, "w").close()
    rows, failed = [], []
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_module, m, log_path) for m in modules]
        for fut in concurrent.futures.as_completed(futures):
            module, rc, seconds = fut.result()
            rows.append((module, rc, seconds))
            if rc:
                failed.append(module)
    rows.sort()
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
            return 0
    elif args.ref:
        return main(["--run"] + changed_paths(args.ref))
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
