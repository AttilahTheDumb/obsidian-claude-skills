# Scenario Corpus

Hand-written fixtures for the parts of the memory pipeline that require semantic
judgment — capture (is this durable?), consolidation (do these merge, coexist, or
contradict?), and reconciliation (which one wins, or is it genuinely ambiguous?). See
`docs/memory-engineering-plan.md`, §6.

## Why these aren't run by `tests/test_memory.py`

That suite covers the deterministic core only — decay math, retrieval scoring, file/index
bookkeeping — none of which needs a model. These scenarios test the *other* half of the
pipeline: whether Claude, following `commands/remember.md` / `commands/compress.md` /
`commands/memory-gc.md`, makes the right call on a given piece of conversation. That
requires actually running the skill against a live model, which a `python3 -m unittest`
run in CI can't do.

Treat this directory as:
- A **manual walkthrough script** — run each scenario's turns through `/remember` or
  `/compress` against a real vault and check the `expect` block by hand.
- A **future automated-eval fixture set** — if this project adds an LLM-graded harness
  later (e.g. driving Claude Code non-interactively and asserting on the resulting
  `Memory/Facts/` state), these are the cases to start from.
- **Documentation of intent** — each scenario is also a concrete, checkable statement of
  what "correct" means for a case the plan calls out by name (§7 risks, §4 stage
  descriptions).

## Scenario format

```yaml
name: short-id
stage: capture | consolidate | reconcile
description: one line, what this is testing and why it's here
turns:
  - "raw conversational input, in order"
expect:
  # stage-specific assertions, see individual files
notes: >
  optional — anything a human grading this by hand should watch for
```

## Metrics (plan §6)

When these are graded (by hand or by a future harness), track:
- **Capture precision** — of facts captured, how many are genuinely durable
- **Capture recall** — of the durable facts planted in a scenario, how many got captured
- **Retrieval precision@5** — needs a populated store + query scenarios (see
  `retrieval-queries.yaml`), not applicable to capture/consolidate/reconcile scenarios
- **Contradiction resolution accuracy** — for `reconcile` scenarios, did the resolution
  (or the decision to flag rather than resolve) match `expect.resolution`

## The stranger test

Independent of any single scenario: replay a session's turns with the memory pipeline
"on" (facts captured, `/resume` retrieving before responding) vs. "off" (fresh context,
nothing preloaded) and diff Claude's responses on a later, related session. If the
responses are indistinguishable, the pipeline isn't doing anything yet regardless of what
the scenario-level metrics say.
