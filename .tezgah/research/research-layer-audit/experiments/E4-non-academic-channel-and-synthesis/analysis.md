# E4 analysis — the grey channel is unnamed but used; synthesis has no home

Raw: `raw/run.txt`, `raw/exploratory-source-naming.txt`, `raw/meta.txt` (protocol
mtime before the run).

## Result

| cell | measured | predicted | verdict |
|---|---|---|---|
| C1 policy | 0 non-academic tokens in the RESEARCH paragraph | 0 | hit |
| C1 skill | 0 in `skills/research/SKILL.md` | 0 | hit |
| C2 | **5 of 14** notes are grey/practice sources | 0 | **MISS** |
| C3 | **0** comparison artifacts | 0 | hit |
| C4 | 0 of 19 Patterns bullets name 2+ sources (protocol token set) | >0 for one line | **MISS** |
| C4x | 2 of 19 bullets name any source at all (post-hoc token set, EXPLORATORY) | - | - |

## The two misses, read honestly

**C2 missed toward a better answer.** The capability is *not* absent from
practice: `product-analysis` holds a Google Research page, a Microsoft page, the
DORA report, an NN/g article and the Playwright docs beside two papers, and its
note 02 records verifying an OpenAlex record against a second source. So the
non-academic channel is real and already used by the line whose question was
practical. What is missing is everything the layer could do about it: no rule
names the channel, no field in a note records the source class, `check` cannot
tell a paper note from a vendor page, and a line that skips the channel entirely
(`judge-positioning`, `typesafe-cost`, `ustam-artifact-contract` - all three with
zero notes) looks identical to one that does it well.

**C4 missed for an instrument reason, and the honest measurement is C4x.** My
protocol's token set wanted ids or author-year; the lines cite sources as bare
short names in parentheses. Re-measured with the post-hoc set, **2 of 19** bullets
name a source at all, both in `infra-candidates`; the other 17 are the line
reasoning about itself. That is the finding: synthesis exists in `findings.md`'s
`## Patterns`, and the sources it rests on are unresolvable prose - neither a
path a checker could resolve nor an id a reader could follow. C4's failure is
therefore an instrument miss on the first pass and a gap on the second, and both
are recorded.

## What the pair means together

The workspace's bootstrap step is documented as "search the literature with more
than one source, save every source ... identify the gap". Measured against the
five lines that exist: two lines have sources, one of those uses the grey channel
unprompted, no line has a place where the sources meet, and 17 of 19 synthesis
bullets cite nothing. The standard the layer wants is the one the MLR literature
writes down - inclusion criteria, a source-quality assessment that distinguishes
formal from grey, and a synthesis that states what the sources agree and disagree
about - and the layer implements none of it as a check.

Rows here are scope: real (the rule text, the skill, and the lines' own literature and findings).
