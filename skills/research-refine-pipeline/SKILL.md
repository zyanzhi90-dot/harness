---
name: research-refine-pipeline
description: 'Continue a Controller-managed run from an accepted Selected Principle through Method refinement and final gates, then plan Full Validation only when the user explicitly initiates it. For pre-convergence science, use idea-discovery.'
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply
---

# Research Refine Pipeline

Continue: **$ARGUMENTS**

## Boundary

This skill composes existing stages without creating a second pipeline or
bypassing a Gate. It starts only from an active Controller-materialized
`idea-stage/SELECTED_PRINCIPLE.yaml`. A Candidate Principle, Human-approved
test set, `PRINCIPLE_EVALUATION.json`, test-only realization, rough Method, or
old report is not a refinement authorization.

The sequence is:

```text
accepted Selected Principle
  -> /research-refine
  -> final method novelty Gate
  -> Top-Venue method strength Gate
  -> final Human Method acceptance
  -> stop at METHOD_CONFIRMED_AWAITING_USER_VALIDATION
  -> only on explicit user initiation: validation-handoff -> /experiment-plan
```

## Preflight

Ask the Controller for status, allowed actions, and allowed agents. Verify the
active accepted Problem/RCA bindings, convergence artifacts, and
`SELECTED_PRINCIPLE.yaml`. Also read the latest return or Full Validation
feedback directed to `method_refinement` and require the refinement execution
to consume it.

If the current phase is `method_design`, `principle_human_selection`,
`principle_test_design`, `principle_test_human_approval`, or
`principle_evaluation`, stop and resume `/idea-discovery`; do not manufacture a
selection or perform Method adaptation early.

## Phase 1 — Method refinement

Invoke `/research-refine`. It must execute:

```text
Selected Principle -> target-domain adaptation -> minimal faithful realization
  -> Principle-only closure -> residual mechanism/adaptation gaps
  -> minimal necessary composition -> Final Scientific Delta Claim
  -> claim-validation obligations
```

Require:

- canonical `refine-logs/FINAL_METHOD_PACKET.json` as the sole scientific
  authority and its deterministic `FINAL_PROPOSAL.md` Human view;
- `refine-logs/FINAL_BLIND_REVIEW.md` from the Controller-issued current review
  request;
- `refine-logs/REFINE_STATE.json`, review summary, and unresolved-issue record.

The formal outcomes are `METHOD_READY`, `REVISE`, `HOLD`, `RETHINK`, and
`RCA_CONFLICT` with the Controller-declared targets. Do not proceed after a
non-accepting verdict.

## Phase 2 — Final novelty, Top-Venue strength, and Human acceptance

Run `/novelty-check "mode: method-final"` against the accepted Selected
Principle, canonical `FINAL_METHOD_PACKET.json`, accepted final method review,
and current formal novelty Evidence/context. The Gate distinguishes method embodiment/
Claim failure (`REVISE_METHOD_DELTA -> method_refinement`), Principle/
Scientific-Delta failure (`RETHINK_PRINCIPLE_DELTA -> method_design`), and
missing novelty Evidence/interpretation (`HOLD -> final_method_novelty_gate`).

Only `NOVEL` opens the independent `top_venue_method_strength_gate`. That Gate
uses the accepted upstream scientific artifacts and the twelve hard dimensions
declared by the canonical workflow; only `TOP_VENUE_READY` reaches the final
Human checkpoint. Human acceptance accepts or
requests revision of the final Method; it does not select a Principle or start
Full Validation. After approval, stop at
`METHOD_CONFIRMED_AWAITING_USER_VALIDATION`.

## Phase 3 — Conditional Full Validation planning

Enter this phase only when the user explicitly initiates Full Validation. Run:

```text
python -m arisctl --root . validation-handoff <run_id>
```

If it fails, stop. If it succeeds, invoke `/experiment-plan` with the live run
ID, workflow hash, handoff hash, artifact bindings, and the exact packet-derived
coverage requirements. The plan must cover every active assumption, condition,
prediction, feasibility obligation, causal chain, RMC, Capability/Obligation,
core Method change, Mechanism Delta, DAG edge, counterfactual, claim element,
and claim/applicability boundary. It must consume
`FINAL_METHOD_PACKET.json`; the deterministic Final Proposal is not a machine
input.

Do not call Principle-discrimination tests from the completed pre-convergence
cycle a substitute for Full Validation. They may be cited only through current
formal Evidence bindings.

## Output summary

Before user-initiated validation, summarize only the final Method artifacts and
the current Controller status. After a successful validation handoff, add links
to `refine-logs/EXPERIMENT_PLAN.md` and `EXPERIMENT_TRACKER.md` plus the first
approved execution action. Never label the Final Scientific Delta Claim as an
Established Scientific Delta; that term is available only after `VALIDATED`.
