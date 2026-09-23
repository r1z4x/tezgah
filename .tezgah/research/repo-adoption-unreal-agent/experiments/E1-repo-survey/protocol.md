# E1 — repo survey of unreallabsai/unreal-agent

**What this is.** A reading pass, not a run. Seven read-only surveys read the
repository at first hand (a full clone at commit `b7c9bf1`, 169 Go files, 61,771
lines under `harness/ internal/ cmd/ benchmarks/`) and compare each subsystem
against tezgah's own surfaces (`hooks/`, `bin/`, `hosts/`, `skills/`,
`.tezgah/research/`). No code is installed, built, imported or executed; no
number this line reports is a measurement of either repository's behaviour.

**The change under consideration.** Nothing is changed by this experiment. It
decides whether *anything* should be.

**What it predicts.** Given tezgah is a hook-based, daemon-less Python layer that
hosts no execution engine, no session store and no scheduler, `PREDICTION:` the
adoptable material is the repository's *decomposition discipline* rather than its
code — specifically that (a) the tool-translator/operation split (a synchronous,
I/O-free validator that emits a serializable operation for asynchronous
execution) names a method tezgah can adopt at zero dependency cost, and (b) the
versioned, forkable session-store and the stable-id input dedup are the two
subsystems tezgah most lacks and would most likely have to build rather than
borrow.

**Why that prediction and not another.** Every prior adoption survey in this
repository (`repo-adoption-gortex-solpi`, `infra-candidates`, `mp-skills-adoption`)
found the borrowable unit to be a shape-of-answer or a discipline, never a
dependency — tezgah's own rule is that the laziest solution that works wins, and a
Go runtime is not lazy for a Python hook layer. A prediction consistent with that
record is the one worth being wrong about.

**What would falsify it.** `FALSIFIED IF:` the surveys find the repository's
value concentrated in machinery that cannot be restated as a rule tezgah could
enforce without the Go runtime — in particular if the operation manager, the
primitives or the coordinator carry no invariant that survives translation into a
hook, a plan file or a skill, and the only honest verdict per subsystem is
"requires a host tezgah does not have". A single subsystem reduced to that
verdict does not falsify the prediction; every subsystem doing so does.

**How the result is read.** Each survey returns candidates with a `file:line`
citation, the invariant it observes, the tezgah surface it would land on, and a
verdict of adopt / adapt / reject with its cost. A candidate with no citation is
dropped, not reported. The prediction is scored as CONFIRMED, PARTIAL or REFUTED
against the falsifier above, after the surveys return.
