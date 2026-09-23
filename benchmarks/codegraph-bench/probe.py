#!/usr/bin/env python3
"""The spike behind plan 010's first acceptance item: the two gaps the codegraph
swap opens, each decided by a measurement rather than by prose, plus the
side-by-side the swap is judged on.

    python3 benchmarks/codegraph-bench/probe.py --gaps      # both, in one run
    python3 benchmarks/codegraph-bench/probe.py --compare   # the two engines

(a) Extensionless sources. `codegraph.json` maps *extensions* to languages, so a
    `bin/tezgah-setup` with no extension has no key to be mapped under. The four
    variants this spike tried are recorded below verbatim with codegraph's own
    rejection line, and the one workaround that measurably works (a `.py`
    symlink) with the count it produced.

(b) The uncovered-file report codegraph does not ship. `--coverage` reads an
    index dump (`codegraph files -j`) and prints, over the tracked files, the two
    classes of gap: a supported extension the index does not hold, and a
    shebang-only script the index cannot key on at all.

(c) The comparison. `--compare` prints, per probe, the codebase-memory-mcp
    number this repo recorded on 2026-09-21 - that engine is gone, so it cannot
    be measured again - against codegraph, which `status`, `callers` and the
    coverage report re-measure live in the same run. Two probes print a recorded
    codegraph number instead: a live index build would rebuild the repository's
    index, and a live blast radius needs a real diff.

Report, not a gate: always exits 0, and prints the index dump it read so an
empty result cannot read as "everything is covered". Stdlib only. The live path
runs `codegraph files -j` through the binary on PATH, or through `npx -y
@colbymchenry/codegraph` when the binary is absent; `--dump <file>` reuses a dump
already taken (what CI does, since the spike must not shell out to npx).
"""
import json
import os
import re
import shutil
import subprocess
import sys

# codegraph's own language table (README "Supported Languages"), used to decide
# which tracked files the index is supposed to hold at all.
SUPPORTED = {
    ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".mjs": "javascript", ".ets": "arkts",
    ".py": "python", ".go": "go", ".rs": "rust", ".java": "java",
    ".cs": "csharp", ".php": "php", ".rb": "ruby", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp", ".m": "objc", ".mm": "objc",
    ".metal": "metal", ".yaml": "yaml", ".yml": "yaml",
}
SHEBANG = re.compile(r"^#!.*\b(python3?|node|bash|sh|ruby|perl)\b")

# 2026-09-21, on a clone of this repo, `codegraph init`, npx -y
# @colbymchenry/codegraph: each key shape and the line codegraph answered with.
MAPPING_ATTEMPTS = (
    ('{"extensions": {"": "python"}}',
     'Ignoring extension mapping in codegraph.json: "" is not a valid file '
     'extension'),
    ('{"extensions": {"bin/tezgah-setup": "python"}}',
     'Ignoring extension mapping in codegraph.json: "bin/tezgah-setup" is not a '
     'valid file extension'),
    ('{"extensions": {"tezgah-setup": "python"}}',
     'Ignoring extension mapping in codegraph.json: "tezgah-setup" is not a '
     'valid file extension'),
    ('ln -s tezgah-setup bin/tezgah-setup.py',
     'indexed: bin/tezgah-setup.py (python, 167 symbols); `callers cbm_command` '
     '-> 5 rows'),
)


def codegraph_argv():
    """The CLI to run: the installed binary, else the npm package the spike used."""
    found = shutil.which("codegraph")
    if found:
        return [found]
    if shutil.which("npx"):
        return ["npx", "-y", "@colbymchenry/codegraph"]
    return []


def codegraph_run(argv, args):
    """One `codegraph` invocation as (stdout, None), or (None, why).

    `args` is the whole argv after the binary: which subcommands take the project
    path as `-p <dir>` and which take it positionally differs (`files` and
    `callers` take the flag, `status` the positional argument), so the caller
    spells it out rather than this helper guessing."""
    if not argv:
        return None, "neither codegraph nor npx is on PATH"
    try:
        done = subprocess.run(argv + list(args), capture_output=True, text=True,
                              timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "codegraph %s failed to run (%s)" % (args[0], exc)
    if done.returncode != 0:
        return None, "codegraph %s exited %d" % (args[0], done.returncode)
    return done.stdout, None


def codegraph_json(argv, args):
    """One `codegraph` invocation parsed as JSON, or (None, why)."""
    blob, why = codegraph_run(argv, args)
    if blob is None:
        return None, why
    try:
        return json.loads(blob), None
    except ValueError as exc:
        return None, "codegraph %s did not print JSON (%s)" % (args[0], exc)


def index_dump(root, argv=None):
    """`codegraph files -j` as text, or (None, why) when it cannot be read.

    `argv` lets a caller that resolves the binary itself (tezgah's pinned
    `TEZGAH_CODEGRAPH_BIN` / config.json, see `bin/tezgah-doctor --coverage`)
    hand one in instead of this module's PATH-then-npx guess."""
    return codegraph_run(argv or codegraph_argv(), ["files", "-j", "-p", root])


def indexed_paths(blob):
    """Every file path in a `codegraph files -j` dump, whatever nesting it uses."""
    out = set()

    def walk(node):
        if isinstance(node, dict):
            path = node.get("path") or node.get("file")
            if isinstance(path, str) and path:
                out.add(path.lstrip("./"))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.endswith(tuple(SUPPORTED)):
            out.add(node.lstrip("./"))

    walk(json.loads(blob))
    return out


def coverage(root, dump_path, argv=None):
    """The two gap classes over `root`'s tracked files, or (None, why).

    `argv` is passed to `index_dump` for a caller that resolves the binary
    itself; `dump_path` reads a dump already taken instead of running the CLI."""
    if dump_path:
        with open(dump_path) as handle:
            blob, why = handle.read(), None
    else:
        blob, why = index_dump(root, argv)
    if blob is None:
        return None, why
    try:
        have = indexed_paths(blob)
    except ValueError as exc:
        return None, "the dump is not JSON (%s)" % exc
    try:
        tracked = subprocess.check_output(["git", "-C", root, "ls-files"],
                                          text=True).split()
    except (OSError, subprocess.SubprocessError) as exc:
        # without git there is no definition of "tracked", and a report that
        # guessed one would read as a coverage number that means nothing
        return None, "git ls-files failed in %s (%s)" % (root, exc)
    by_ext, by_shebang, twins = [], [], []
    for rel in tracked:
        ext = os.path.splitext(rel)[1].lower()
        if ext in SUPPORTED:
            if rel not in have:
                by_ext.append((rel, SUPPORTED[ext]))
            continue
        if ext in ("", ".sh"):
            try:
                with open(os.path.join(root, rel), errors="ignore") as handle:
                    first = handle.readline()
            except OSError:
                continue
            found = SHEBANG.match(first)
            if found:
                # the swap's answer to the extensionless file: a `.py` twin the
                # index can key on. A shell script has no twin to make - codegraph
                # ships no shell parser - so it stays in the uncovered list.
                (twins if rel + ".py" in have else by_shebang).append(
                    (rel, found.group(1)))
    return {"tracked": len(tracked), "indexed": len(have),
            "by_ext": by_ext, "by_shebang": by_shebang, "twins": twins}, None


def thousands(n):
    """A node/edge count as the recorded numbers write it: 15 013, not 15013."""
    return "{:,}".format(int(n)).replace(",", " ")


def mib(n):
    return "%.1f MiB" % (float(n) / (1024 * 1024))


def live_index(root, _dump_path):
    """Node, edge and db-size numbers straight from the live index."""
    data, why = codegraph_json(codegraph_argv(), ["status", "-j", root])
    if data is None:
        return None, why
    return ("%s nodes, %s edges, %s db"
            % (thousands(data.get("nodeCount") or 0),
               thousands(data.get("edgeCount") or 0),
               mib(data.get("dbSizeBytes") or 0))), None


def live_callers(root, symbol):
    """The callers codegraph names for `symbol`, live."""
    data, why = codegraph_json(
        codegraph_argv(), ["callers", symbol, "-j", "-p", root, "-l", "50"])
    if data is None:
        return None, why
    names = [c.get("name") for c in (data.get("callers") or []) if c.get("name")]
    if not names:
        return "no callers", None
    shown = ", ".join(names[:4]) + (", ..." if len(names) > 4 else "")
    return "%d caller(s): %s" % (len(names), shown), None


def live_coverage(root, dump_path):
    """The coverage counts of the same report `--gaps` prints in full."""
    report, why = coverage(root, dump_path)
    if report is None:
        return None, why
    return ("%d tracked files, %d in the index, %d uncovered (%d supported "
            "extension, %d shebang-only, %d through a `.py` twin)"
            % (report["tracked"], report["indexed"],
               len(report["by_ext"]) + len(report["by_shebang"]),
               len(report["by_ext"]), len(report["by_shebang"]),
               len(report["twins"]))), None


# The five probes, in the order the plan lists them. `cbm` is what this repo
# recorded on 2026-09-21; `codegraph` is the number recorded beside it, printed
# when `live` cannot answer; `held_back` names the part of a row a live
# re-measurement cannot produce.
COMPARE = (
    {"probe": "index build and size",
     "cbm": "7.9 s to build, 33 MB db, 15 013 nodes, 33 245 edges",
     "codegraph": "about 1 s to build, 13.8 MiB db, 4 373 nodes, 13 230 edges",
     "live": live_index,
     "held_back": "the build time (re-measuring it rebuilds the index)"},
    {"probe": "callers of `classify_prompt`",
     "cbm": "5, transitive",
     "codegraph": "2, direct plus its test",
     "live": lambda root, dump: live_callers(root, "classify_prompt"),
     "held_back": None},
    {"probe": "callers of `hooks.tezgah_context.record`",
     "cbm": "0 - the engine missed them",
     "codegraph": "found them (host hooks, triage, docs)",
     "live": lambda root, dump: live_callers(root, "record"),
     "held_back": None},
    {"probe": "blast radius of a docstring-only diff",
     "cbm": "5 impacted",
     "codegraph": "11 affected",
     "live": None,
     "why": "a live measurement needs a real diff in the repo",
     "held_back": None},
    {"probe": "uncovered files",
     "cbm": "partial parses reported, never the file list",
     "codegraph": "nothing reported - `status` counts what it parsed, never "
                  "what it skipped",
     "live": live_coverage,
     "held_back": None},
)


def compare(root, dump_path):
    """Print both columns per probe: cbm recorded 2026-09-21, codegraph live.

    The codegraph half is re-measured now wherever the CLI answers. Where it
    cannot, the recorded number is printed and labelled as recorded, because a
    silent fallback would read as a measurement."""
    print("== probe comparison: codebase-memory-mcp (recorded 2026-09-21) "
          "against codegraph (live on %s)" % root)
    for row in COMPARE:
        print("\n  %s" % row["probe"])
        print("    codebase-memory-mcp (recorded 2026-09-21)  %s" % row["cbm"])
        if row["live"] is None:
            print("    codegraph (live)                           not re-measured "
                  "here: %s" % row["why"])
            print("    codegraph (recorded 2026-09-21)            %s" % row["codegraph"])
            continue
        value, why = row["live"](root, dump_path)
        if value is None:
            print("    codegraph (live)                           unavailable: %s"
                  % why)
            print("    codegraph (recorded 2026-09-21)            %s" % row["codegraph"])
        else:
            print("    codegraph (live)                           %s" % value)
            if row["held_back"]:
                print("    codegraph (recorded 2026-09-21)            %s  [%s]"
                      % (row["codegraph"], row["held_back"]))
    print("\n  the gate: no probe may come out worse for codegraph except the "
          "coverage probe, which codegraph does not ship at all - this spike "
          "owns it and `bin/tezgah-doctor --coverage` ships it.")
    return 0


def gaps(root, dump_path):
    """Gap (a) and gap (b) as text."""
    print("== gap (a): an extensionless source under bin/")
    for written, answered in MAPPING_ATTEMPTS:
        print("   wrote %s\n     -> %s" % (written, answered))
    print("   fallback: declare the gap in the contract text and let gap (b) list "
          "the files, or add a `.py` symlink per script (counted below).")
    print("\n== gap (b): the uncovered-file report")
    report, why = coverage(root, dump_path)
    if report is None:
        print("   could not read an index dump: %s" % why)
        print("   fallback: pass --dump <codegraph files -j output>.")
        return 0
    print("   tracked files: %d | files in the index: %d"
          % (report["tracked"], report["indexed"]))
    print("   uncovered, supported extension (%d):" % len(report["by_ext"]))
    for rel, lang in report["by_ext"]:
        print("      %s (%s)" % (rel, lang))
    print("   uncovered, shebang-only script (%d):" % len(report["by_shebang"]))
    for rel, lang in report["by_shebang"]:
        print("      %s (%s)" % (rel, lang))
    print("   covered through a `.py` twin (%d):" % len(report["twins"]))
    print("   fallback: ship this as `bin/tezgah-doctor --coverage`; a tracked "
          "file is covered when the index holds it or a `.py` twin does, and a "
          "shell script is named as out because codegraph ships no shell parser.")
    return 0


def main():
    argv = sys.argv[1:]
    root = "."
    dump_path = None
    if "--root" in argv:
        root = argv[argv.index("--root") + 1]
    if "--dump" in argv:
        dump_path = argv[argv.index("--dump") + 1]
    if "--compare" in argv:
        compare(root, dump_path)
        if "--gaps" not in argv:
            return 0
    return gaps(root, dump_path)


if __name__ == "__main__":
    sys.exit(main())
