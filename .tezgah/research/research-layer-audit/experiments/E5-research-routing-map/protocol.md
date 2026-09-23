# E5 protocol — where the research rule reaches a session, and what the status mark sees

**Ordering disclosed.** The brief below was issued to a read-only discovery agent
*verbatim and before* it ran; the file itself was written afterwards, by the
session that received the result, because a read-only agent cannot write. This
file is therefore the brief, not a prediction, and no prediction is claimed for
it.

## Brief issued

> For each host tezgah supports (claude, codex, cursor, opencode, dsh, omp): does
> a research-class prompt get the research rule injected, and through which
> mechanism (UserPromptSubmit hook, system prompt, skill router file, nothing)?
> Name the file and line that decides it. Then: does each host's status line show
> a `research` measure, and what command makes it "used"? Name every host where a
> research task would NOT be told to route through orx, and why. Cite `path:line`
> for every claim; say "unverified" rather than guessing.

## Metric

- hosts that arm `research` at prompt time and the mechanism, with `path:line`;
- hosts that render the `research` measure;
- the set of shell commands that light the measure, and whether the layer's own
  CLI (`bin/tezgah-research`) is among them;
- host names where the orx manual cannot be loaded, and why.

## Baseline / threshold

The contract promises the rule is armed per prompt and that the host says the
same thing (`hooks/tezgah_policy.py:1-11`). Anything less, per host, is the
finding.

## What would falsify

- a host with no research routing at all: the "all six" claim fails;
- the measure lighting from a non-shell source: the orx-only claim fails;
- the cited line not showing what the row says it shows.
