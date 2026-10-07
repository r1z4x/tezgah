#!/usr/bin/env python3
"""Deploy the phase-1 arms of plan 062 as template HOMEs, out of tree.

    python3 homes.py deploy --lab DIR [--commit REV]

Every arm is a HOME directory, never the real one: `bench.py run` copies an
arm's template into a fresh per-run HOME, so a switch one run creates cannot
reach the next run, and no run reads or writes the operator's host config.

The harness is pinned: `git archive REV` of this repository is unpacked into
`DIR/src/<sha>/` and every armed HOME is installed from that copy
(`bin/tezgah-setup --install --hosts omp --no-deps`), so the arm is a commit,
not whatever the checkout holds when a run starts.

    p1-bare           an empty HOME: no RULES.md, no bridge, no ledger
    p1-full           the omp install from the pinned copy
    p1-noswitch       p1-full with every injected unlock stripped (unlocks.py):
                      RULES.md, every skill's markdown, and - through
                      TEZGAH_PYTHON (arms.json) - every hook answer
    p1-verify-off     p1-full plus the `verify-off` switch file
    p1-reminder-off   p1-full plus the `reminder-off` switch file

`DIR/homes/MANIFEST.json` records the commit, each arm's RULES.md sha256, the
unlocks left in each arm's injected text (0 for p1-noswitch, by construction
checked here) and the switch files each template holds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ARMS = ("p1-bare", "p1-full", "p1-noswitch", "p1-verify-off", "p1-reminder-off")
SWITCHED = {"p1-verify-off": "verify-off", "p1-reminder-off": "reminder-off"}
# the variables a path resolver reads (lessons: a sandbox that resets HOME but
# not these still reaches real config)
DROP_ENV = ("CODEX_HOME", "DSH_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
            "XDG_CONFIG_HOME", "TEZGAH_OPENCODE_DATA", "PI_CODING_AGENT_DIR",
            "TEZGAH_ROOTS", "TEZGAH_PREFIX")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_source(lab: Path, rev: str) -> tuple[Path, str]:
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", rev], check=True,
                            capture_output=True, text=True).stdout.strip()
    src = lab / "src" / commit
    if not (src / "bin" / "tezgah-setup").is_file():
        src.mkdir(parents=True, exist_ok=True)
        archive = subprocess.run(["git", "-C", str(REPO), "archive", commit],
                                 check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(src)], input=archive, check=True)
    return src, commit


def install(src: Path, home: Path, runs: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    env.update(HOME=str(home), TEZGAH_NO_DEPS="1")
    proc = subprocess.run(
        [sys.executable, str(src / "bin" / "tezgah-setup"), "--install", "--hosts", "omp",
         "--no-deps", "--roots", str(runs)],
        env=env, capture_output=True, text=True, timeout=600)
    (home.parent / ("%s.install.log" % home.name)).write_text(proc.stdout + proc.stderr)
    if proc.returncode != 0:
        sys.exit("install into %s failed (rc=%d), see %s.install.log"
                 % (home, proc.returncode, home))


def strip_home(home: Path, src: Path) -> int:
    """p1-noswitch: strip RULES.md and every skill's markdown; the residue left."""
    sys.path.insert(0, str(src / "benchmarks" / "arm-bench"))
    import unlocks
    agent = home / ".omp" / "agent"
    rules = agent / "RULES.md"
    rules.write_text(unlocks.strip(rules.read_text(encoding="utf-8")), encoding="utf-8")
    left = len(unlocks.residue(rules.read_text(encoding="utf-8")))
    skills = agent / "skills"
    for link in sorted(skills.iterdir()):
        target = link.resolve()
        if link.is_symlink():
            link.unlink()
        else:
            shutil.rmtree(link)
        shutil.copytree(target, link, symlinks=False)
        for md in link.rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="replace")
            stripped = unlocks.strip(text)
            if stripped != text:
                md.write_text(stripped, encoding="utf-8")
            left += len(unlocks.residue(stripped))
    return left


def injected_unlocks(home: Path, src: Path) -> int:
    sys.path.insert(0, str(src / "benchmarks" / "arm-bench"))
    import unlocks
    rules = home / ".omp" / "agent" / "RULES.md"
    return len(unlocks.residue(rules.read_text(encoding="utf-8"))) if rules.is_file() else 0


def switches(home: Path, src: Path) -> list[str]:
    sys.path.insert(0, str(src / "hooks"))
    import tezgah_paths
    found = []
    for d in (home / ".config" / "tezgah", home / ".claude"):
        found += [str((d / n).relative_to(home)) for n in tezgah_paths.SWITCHES if (d / n).exists()]
    return found


def cmd_deploy(args) -> int:
    lab = Path(args.lab).resolve()
    if REPO in lab.parents or lab == REPO:
        sys.exit("--lab must be outside the repository (%s)" % REPO)
    src, commit = pinned_source(lab, args.commit)
    runs = lab / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    homes = lab / "homes"
    homes.mkdir(parents=True, exist_ok=True)
    manifest = {"commit": commit, "source": str(src), "runs": str(runs), "arms": {}}
    for arm in ARMS:
        home = homes / arm
        if home.exists():
            # only a template this generator made: it carries its own marker
            if not (home / ".armbench-template").is_file():
                sys.exit("%s exists and is not a template this script made" % home)
            shutil.rmtree(home)
        home.mkdir()
        (home / ".armbench-template").write_text(arm + "\n")
        entry = {}
        if arm != "p1-bare":
            install(src, home, runs)
        if arm in SWITCHED:
            (home / ".config" / "tezgah" / SWITCHED[arm]).write_text("")
        if arm == "p1-noswitch":
            entry["stripped_residue"] = strip_home(home, src)
            if entry["stripped_residue"]:
                sys.exit("p1-noswitch: %d unlock(s) left after stripping"
                         % entry["stripped_residue"])
        rules = home / ".omp" / "agent" / "RULES.md"
        entry["rules_sha256"] = sha(rules) if rules.is_file() else None
        entry["rules_unlocks"] = injected_unlocks(home, src)
        entry["switches"] = switches(home, src)
        manifest["arms"][arm] = entry
        print("%-17s rules=%s unlocks=%d switches=%s"
              % (arm, (entry["rules_sha256"] or "none")[:12], entry["rules_unlocks"],
                 ",".join(entry["switches"]) or "-"))
    (homes / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("commit %s -> %s" % (commit, homes / "MANIFEST.json"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("deploy")
    p.add_argument("--lab", required=True)
    p.add_argument("--commit", default="HEAD")
    p.set_defaults(func=cmd_deploy)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
