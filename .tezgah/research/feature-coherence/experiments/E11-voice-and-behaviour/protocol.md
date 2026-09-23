# E11 - are the two empty evidence classes reachable at all

## What changes
Nothing. Across every arm, `user-verbatim` and `behaviour` were empty, and the arms
said so. This experiment asks whether any source in either repository could have
produced them, so the empty class becomes a finding about the product rather than a
gap in the analysis.

## Method
For each of the two audited repositories, look for: an analytics or telemetry
initialisation (by config, dependency, or a `Noop`-style sink), a ticket or support
export, a review corpus, an audit-log table that could serve as a behaviour proxy with
its retention, and any user-facing feedback capture. Cite `path:line` for each finding,
and name the number each source can support and the one it leaves out.

## Predicts
Both repositories carry audit logs, while analytics is absent from both: so
`behaviour` is reachable only as an audit-derived count with its window and definition,
and no funnel can be computed; `user-verbatim` has no source in either repository.

## Falsification criterion
A source that could yield a verbatim user statement (a ticket export, a review
attachment, a feedback table with text) would falsify the second half.
