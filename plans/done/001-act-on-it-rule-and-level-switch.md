---
id: 001
title: arm the act-on-it rule, make the ponytail level real, and stop the status marks lying
status: done
branch: main
pr:
created: 2026-09-18
updated: 2026-09-18
---
## Goal
Make the ponytail intensity level a stored switch instead of a phrase in a
document, add the vendored act-on-it (i-have-adhd) rule as a first-class
always-on rule with its own switch and status mark, and make the status line's
`pony`/`adhd` marks report what they can actually observe.

## Acceptance
- [x] `tezgah-pony lite|full|ultra` sets the level; a non-default level rides the
      per-turn reminder; `full` (the default) costs no characters
      (tests/test_context.py:PonyLevel, live render on the installed path)
- [x] `tezgah-adhd on|off` disarms/arms the rule and the paragraph leaves the
      injected text (tests/test_context.py:AdhdSwitch)
- [x] `skills/i-have-adhd/SKILL.md` exists, resolves on all six hosts, and the
      installer's `SKILLS` list is pinned against disk (tests/test_skills.py)
- [x] `pony`/`adhd` flip from armed to in-force only where the read is
      observable (claude, opencode, omp) and state nothing (dim) elsewhere
      (tests/test_context.py:StatusCli, tests/test_codex_hook.py)
- [x] `ruff check .` clean, `python3 -m unittest discover -s tests` green,
      `tezgah-setup --install` and `--sync` exit 0, plugin copy byte-identical

## State
Landed on main (no branch): 25 files changed, 641 insertions, plus four new
paths (bin/tezgah-pony, bin/tezgah-adhd, commands/, skills/i-have-adhd/).
Two upstream rules were rewritten rather than imported verbatim, because they
collided with rules already in force: the state restatement points at the todo
list, and a time estimate is marked as an estimate (the integrity rule).
The consult panel had rejected the rule as a contract collision; the user's call
was to arm it, and the collision was resolved by rewriting the two rules.
The skill file itself was missing for part of the session because a write result
was replaced by a harness notice - the installer's `islink` check called the
dangling links installed, which is now fixed (skills_linked()).

## Next
- none (done). Follow-ups live in plan 002.
