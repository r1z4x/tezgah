# E5 - the same measurement on a second feature, in a different stack

## What changes

Nothing in either repository. This experiment repeats the E1+E2+E3 shape on a second
feature to test whether the class split is structural or an artefact of the first
stack.

Target: `/Users/rizax/Projects/aibim-app`, the admin **Users** area. Stack, read from
the manifests: Rust (edition 2021) with axum 0.8 + sqlx 0.8 + Postgres
(`admin/backend/Cargo.toml`), a React 19 + Vite SPA (`admin/frontend/package.json`),
routes registered at `admin/backend/src/main.rs:255-286` and a committed SQL schema in
`db/migrations/`. Nothing in common with target #1 (Next.js server components + NestJS
+ Prisma) except that both are admin CRUD surfaces.

## Method

1. **E5a - freeze a corpus** of defect rows across the same ten classes, by reading
   the capability path (route -> handler -> authorization -> query -> table) and the
   SPA surface that calls it. Every row carries a `path:line` and a class. The corpus
   is frozen before any rater runs and its sha256 is recorded.
2. **E5b - baseline arm**: two independent rater contexts apply the shipped
   `product-analysis` rubric to the same feature, blind to the corpus.
3. **E5c - treatment arm**: two independent rater contexts apply
   `skills/feature-audit/SKILL.md`, same blindness, same environment.
4. Score both arms against the frozen corpus with the E2 scoring rule.

Environment for both arms: the same machine, the same permission to read and to try
to start the stack. The app needs a Docker build of a Rust and a Node image
(`make admin-dev`); if neither arm can start it in the time available, that is a
shared constraint and both arms are code-scope - and it is reported, because two of
the ten classes (data-view layout, destructive-confirmation content) were reachable
only through the running app on target #1.

## Predicts

- The second stack shows the **same shape**: the baseline arm's union lands at or
  below half the in-scope classes, the treatment arm's union at least two classes
  above it, and the classes the baseline misses include the field contract and the
  capability-change slot.
- The treatment arm again writes at least one capability-change proposal where the
  baseline writes none.

## Falsification criterion

A baseline union at or above the treatment union on this feature would falsify the
transfer claim, and the line would then say that the first feature's result does not
generalise. A treatment union that exceeds the baseline only by classes the *running*
app supplies, when this feature was audited from code, would weaken it to the point
of a reported non-result.

## Why

One feature is one data point. The class split is claimed to be structural - a
screen-level method cannot express a layer disagreement - and a structural claim that
holds in exactly one repository is indistinguishable from a coincidence of that
repository's shape.
