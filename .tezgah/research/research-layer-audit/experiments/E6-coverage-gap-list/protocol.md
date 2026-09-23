# E6 protocol — what the research layer's test suite does not pin

**Ordering disclosed.** Same shape as E5: the brief was issued verbatim before
the agent ran, the file is written afterwards by the session that received the
result, because a read-only agent cannot write.

## Brief issued

> List every test that touches the research layer, grouped by what behaviour it
> pins. Then list concrete behaviours the code implements or documents that NO
> test pins - the gap list. Cite the test names and the code `path:line` they
> would have covered. Also state which of these are covered by other suites
> rather than `tests/test_research.py`. For each gap name what a failing
> implementation would look like and which existing helper would have been
> reused.

## Metric

- number of behaviour groups pinned, with the test method and the `def` line;
- number of unpinned behaviours, each with the code `path:line` and the doc
  phrase that promises it.

## Baseline / threshold

The standard for a load-bearing layer in this repository is the one the other
suites follow: every documented refusal has a test that fails when the refusal
goes. Measured as a count, not a bit.

## What would falsify

- a gap that turns out to be covered by a suite the agent did not read: the
  count drops and the row is corrected;
- a "gap" that is not promised anywhere in code or docs: it is not a gap and is
  removed.
