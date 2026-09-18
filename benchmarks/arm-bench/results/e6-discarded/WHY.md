# Why these rows are not the block

They were recorded by the first launch of the E6 block, which ran 16 jobs each
covering one repeat chunk of an arm at `k=100`. The provider serves about 1.9
rows a minute regardless of local concurrency (measured twice), so that design
was 3.5 hours; the block was re-launched at `k=25` per arm (see amendment 2 of
`../PREREGISTRATION-E6.md`).

Only the `.c0` rows - repeats 1-25 - fall inside the design, and they are in
`results/e6/`. The rows here are repeats 26-77: outside the design, excluded
from every endpoint, and kept rather than deleted because a spent run that is
quietly dropped is indistinguishable from one that never happened.
