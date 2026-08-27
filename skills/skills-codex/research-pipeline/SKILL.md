---
name: research-pipeline
description: "Canonical downstream research continuation. Use only with a Controller-managed run ID that has reached formal method acceptance and when the user explicitly starts validation. It consumes approved artifacts to plan and execute validation; it never discovers, selects, or approves an idea."
argument-hint: "<canonical-run-id>"
allowed-tools: Bash(*), Read, Grep, Glob, Skill
---

# Canonical Research Continuation: Approved Method -> Validation

`/research-pipeline` is a downstream orchestrator, not a research-entry or
idea-selection workflow. Its only input is a canonical Controller run ID. A
broad direction, idea title, ranked idea, pilot result, old report, template,
or free-text method is not a substitute for that ID or its approved artifacts.

The user's invocation of this skill is the explicit request to begin validation.
It does not create an additional approval, state machine, stage, or Gate.

## Required preflight

Before invoking any downstream skill, ask the Controller to issue the formal
validation handoff:

```bash
python -m arisctl --root . validation-handoff <run_id>
```

Proceed only when this command succeeds. It is the sole formal entry to this
pipeline: it records the user's validation start and verifies that the run is in
`METHOD_CONFIRMED_AWAITING_USER_VALIDATION`, with the accepted problem,
root-cause analysis and verdict, Controller-materialized Selected Principle,
final method proposal, novelty verdict, human method acceptance, provenance,
and current artifact hashes. Consume the returned `validation_obligations`:
causal chains, Required Mechanism Changes, Required Capabilities/Design
Obligations, selected Principle intervention, core method changes, predicted
mechanism changes, failure/applicability boundaries, Final Scientific Delta
Claim, and claim-validation obligations.

Record and pass forward only the returned run ID, workflow hash, **handoff
hash**, artifact hash map, and artifact paths. Do not recreate, infer, replace, or supplement
any of these formal artifacts from the prompt or workspace files.

## If preflight does not pass

Stop. Do not invoke `/idea-discovery`, `/idea-creator`, `/novelty-check`,
`/research-refine`, `/experiment-plan`, or `/experiment-bridge`; do not create
an experiment plan, pilot, implementation, review loop, or a second pipeline
state. In particular, this skill must not use `tools/run_state.py` to start,
resume, accept, or advance a research workflow.

Report the Controller result and direct the user to resume the canonical route:

```bash
python -m arisctl --root . status <run_id>
python -m arisctl --root . allowed-actions <run_id>
python -m arisctl --root . allowed-agents <run_id>
```

The user must complete the indicated canonical phase or Gate. There is no
timeout approval, automatic choice of a ranked idea, or fallback to an
ad-hoc/legacy path inside `/research-pipeline`.

## Execution sequence after a successful preflight

1. Invoke `/experiment-plan` with the canonical run ID and the handoff bindings.
   That skill repeats `validation-handoff`, consumes only the returned formal
   artifacts, and records the same run ID, workflow hash, and artifact-hash map
   in `EXPERIMENT_PLAN.md`.
2. Invoke `/experiment-bridge` with that bound formal plan and the same run ID.
   It repeats the preflight and refuses implementation if the plan bindings or
   formal artifacts have changed.
3. When results are available, invoke `/result-to-claim` using the bound plan,
   results, mechanism-validation evidence, and the handoff hash. It creates one
   validation-result JSON with the same run ID, workflow hash and handoff hash,
   then the user explicitly submits it through:

   ```bash
   python -m arisctl --root . submit-validation-result <run_id> VALIDATION_RESULT.json
   ```

   Its fixed outcomes are `VALIDATED` (formally close validation and record the
   Established Scientific Delta), `METHOD_REFINEMENT_REQUIRED` (the Selected
   Principle remains valid, but its concrete Method/Claim requires revision),
   `SELECTED_PRINCIPLE_REJECTED` (return to Principle formation),
   `ROOT_CAUSE_REJECTED` (return to root-cause analysis), and
   `PROBLEM_PREMISE_REJECTED` (reopen problem generation). The
   Controller archives and invalidates the affected downstream canonical
   artifacts; this skill never chooses a target itself.

If a downstream check exposes a diagnosis or method conflict, preserve the
evidence in the bound result and submit only its fixed Controller decision;
never silently reframe the research or select a new idea here.

## Boundary

`/research-pipeline` does not operate in `NON_CANONICAL_AD_HOC` mode. Explicit
standalone experiments remain the responsibility of their dedicated skills and
must retain that non-canonical label; they cannot be presented as continuation
of this canonical pipeline.

This skill does not autonomously run an auto-review loop, generate a narrative
report, or start paper writing. Those are separate user-initiated tasks after
their own evidence and review requirements are satisfied.
