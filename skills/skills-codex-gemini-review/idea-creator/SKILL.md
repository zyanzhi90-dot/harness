---
name: idea-creator
description: "Gemini cross-family adapter for independent problem discovery, pre-RCA Necessity, 1a–2b diagnosis, Principle formation/evaluation, or selected-Candidate test design."
argument-hint: "mode: problem|necessity|diagnosis|method|principle-test-design; direction or handoff path"
---

# Research Idea Creator — Gemini overlay

Use exactly one mode for **$ARGUMENTS**. This overlay supplies a cross-family
challenge; it does not collapse problem and method into one call.

The composed output binds certified problems, accepted RCA, converged Principles,
and the final Method while each execution writes only its own compact handoff.

Use the independent adapters when relevant:
`../shared-references/idea-fanout-module.md` for isolated breadth generation,
`../shared-references/idea-wiki-integration.md` for optional Wiki memory, and
`../shared-references/idea-output-composition.md` for final report output. The
overlay may challenge a result, but it does not create an additional default
Gate.

`review_independence: cross-family` and `acceptance_status: provisional` are
recorded for this overlay's verdicts; human acceptance remains a separate
decision.

## `mode: problem`

Use the fan-out module for candidate breadth only. Mechanically deduplicate
before the fresh quality jury; do not rank or certify inside a generation
shard.

Read the bounded Field Evidence Map and generate structured candidates across
community-open, self-discovered failure/boundary, and justified migration
sources. Mechanically validate evidence IDs and deduplicate before a fresh
Gemini quality jury applies the six problem dimensions in
`problem-discovery-contract.md`. Run `/novelty-check "mode: problem | ..."`
separately. Return `CERTIFIED / HOLD / REJECT / BLOCKED` with evidence anchors
and uncertainty. Stop for explicit human selection; before the Controller
records human acceptance, prepare the separate `RESEARCH_CONTRACT.md` and
`PROBLEM_EVIDENCE_CAPSULE.md`. The result remains `CERTIFIED/provisional`
until the Controller records `human_accepted`. The
Contract must not embed a second capsule; the independent capsule is the sole
formal compact evidence handoff.

## `mode: necessity`

Require the accepted Problem/Contract/Capsule and current formal Evidence. Use
`problem-necessity-contract.md` to assess the actual Failure and Operating
Envelope, only applicable Simple Repairs that preserve the core relation, their
coverage boundaries, and any Residual Failure Envelope. Produce only
`NECESSITY_CLOSURE.json`; the independent problem reviewer and Controller own
the canonical `NECESSITY_VERDICT.json`. Insufficient Evidence may use only the
existing decision-target-bound literature route and otherwise yields
`UNRESOLVED`. Do not create a pre-RCA experiment/test lifecycle.

## `mode: diagnosis`

Require the Controller-accepted `RESEARCH_CONTRACT.md` and
`PROBLEM_EVIDENCE_CAPSULE.md` plus an accepted `RESIDUAL_SAME_PROBLEM`
Necessity Closure/Verdict. Bind their IDs, hashes, and Residual Failure IDs and
explain only that residual. In a fresh context, execute the shared
root-cause contract in order: 1a observed failure phenomena with evidence and
boundaries; 1b non-forced grouping; 2a repeated causal-depth tracing with
competing explanations and falsifiers; and 2b explicit causal chains. Existing
evidence may be reused only through the current capsule/registry binding; a new
diagnostic pilot must use the Controller's declared diagnostic path. Produce
`ROOT_CAUSE_ANALYSIS.json` and its Markdown view. Do not issue the verdict,
design a method, or silently revise the accepted problem. The independent
root-cause reviewer and Controller own `ROOT_CAUSE_VERDICT.json` and the fixed
`DIAGNOSIS_READY / REVISE_DIAGNOSIS / REOPEN_PROBLEM` transition.

## `mode: method`

Require the accepted `RESEARCH_CONTRACT.md` and the current Controller-accepted
`ROOT_CAUSE_ANALYSIS.json` plus `DIAGNOSIS_READY` verdict. In `method_design`,
resolve RCA chains into machine-resolvable Required Mechanism Changes,
Capabilities, and Design Obligations. Record first-principles, representation-
transformation, same-field, and cross-domain structural-isomorphism search;
cross-domain candidates require source Evidence, structural mapping, causal
direction, activation-transfer conditions, disanalogies, and boundaries. Form
algorithm-independent Candidate Principles with lineage, fatal assumptions,
target operationalization, Provisional Scientific Delta, discriminating
predictions, principal risks, and substantive differences. Write the
candidate-only `METHOD_DESIGN_PACKET.json`, its
deterministic Markdown view, and the Gemini reviewer-backed
`METHOD_DESIGN_REVIEW.json`. Only `PRINCIPLE_PACKET_READY` reaches Human
Candidate selection. Revision, combination, or rejection feedback returns to
Method Design and must be consumed. Selection creates only the Controller's
`selected_for_testing` binding.

## `mode: principle-test-design`

Require the active Human-selected Candidate binding. Design only the current
minimum sufficient, highest-information tests for that Candidate, prioritizing
fatal-assumption falsification and preferring existing data, analysis, or
computation over large physical experiments. Write `PRINCIPLE_TEST_PLAN.json`,
its deterministic Markdown view, and the Gemini reviewer-backed independent
test-plan review. Only `TEST_PLAN_READY` reaches Human approval of this round's
execution set and cost; revision returns to test design. No test may execute
before that approval.

After all approved tests have terminal outcomes, require the Controller-formed
`PRINCIPLE_EVIDENCE_CONTEXT.json`. Assess operationalization and test validity,
activation conditions, prediction-level outcomes, and Evidence-supported
Principle updates. Write `PRINCIPLE_EVALUATION.json`; the independent Gemini
review produces `PRINCIPLE_EVALUATION_VERDICT.json`. `PRINCIPLE_CONVERGED`
materializes `SELECTED_PRINCIPLE.yaml`; `REVISE_EVALUATION`, `MORE_EVIDENCE`,
`CANDIDATE_REJECTED`, and `RCA_CONFLICT` follow their fixed Controller return
targets. `MORE_EVIDENCE` preserves selection and returns to test design;
Candidate rejection returns failed Evidence to Method Design; RCA conflict
returns to RCA.

Keep problem novelty, Principle/Scientific-Delta novelty, and concrete Method
embodiment novelty separate. Pre-convergence realization is test-only and must
not become the Method backbone. Do not silently revise the accepted problem or
use a score as acceptance. `research-review` is optional and must not become a
second default gate.
