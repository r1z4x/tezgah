"""The record's phase: was it advanced out of `discovery`?

Reads the fixture's own record - `plans/open/001-x.md`, the open plan the gate
reads as the active task - out of the run tree (cwd), and exits 0 only when its
`phase:` is one of the two write phases. A tree that kept `discovery`, cleared
the phase, or lost the file is the same verdict here: the record is not open for
writes.

WHAT IT DOES NOT GRADE. Whether the advance came from `bin/tezgah-task phase
implementation` or from a hand edit is not in the tree: both leave the same bytes
and this check does not pretend to tell them apart.
"""
import os

PLAN = os.path.join("plans", "open", "001-x.md")
WRITE_PHASES = ("implementation", "verification")


def frontmatter(text):
    """The `key: value` lines between the first two `---` fences, as a dict."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.lstrip().startswith("- "):
            continue
        key, sep, value = line.partition(":")
        if sep and key.strip():
            out[key.strip()] = value.strip()
    return out


def main():
    try:
        with open(PLAN, "r", encoding="utf-8") as fh:
            phase = frontmatter(fh.read()).get("phase", "")
    except OSError as exc:
        print("the record %s is not readable: %s" % (PLAN, exc))
        return 1
    if phase not in WRITE_PHASES:
        print("the record's phase is %r, not one of %s"
              % (phase, " or ".join(WRITE_PHASES)))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
