---
name: "research-refine"
description: "Gemini cross-family review overlay for adapting one Controller-materialized Selected Principle into a minimal faithful Method and bounded Final Scientific Delta Claim."
---

> Install after `skills/skills-codex/*`.
> `review_independence: cross-family`.

# Research Refine — Gemini Review Overlay

Refine: **$ARGUMENTS**

## Scientific contract

Load:

- [`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
- [`method-design-contract.md`](../shared-references/method-design-contract.md)
- [`method-refinement-protocol.md`](../shared-references/method-refinement-protocol.md)
- [`reviewer-independence.md`](../shared-references/reviewer-independence.md)

Preserve the accepted Problem/RCA/RMC/Capability/Obligation bindings and the
Controller-materialized `idea-stage/SELECTED_PRINCIPLE.yaml`. Adapt that
Principle to the target domain, derive its minimal faithful realization, attempt
Principle-only closure, identify concrete residual adaptation/mechanism gaps,
and add only the minimal composition necessary to close named gaps. Bound the
Final Scientific Delta Claim and its validation obligations without treating it
as established before Full Validation.

Require accepted convergence artifacts and the active Selected Principle; do
not treat a pre-convergence realization, prose proposal, or `IDEA_REPORT.md` as
a valid precondition. Final method novelty is checked only after
`FINAL_PROPOSAL.md`.

## Outputs

Preserve:

- `REFINE_STATE.json`
- `ACTIVE_PROPOSAL.md`
- `UNRESOLVED_ISSUES.md`
- `round-N-review.md`
- `round-N-decision.md`
- `FINAL_BLIND_REVIEW.md`
- `FINAL_PROPOSAL.md`
- `REVIEW_SUMMARY.md`
- `REFINEMENT_REPORT.md`

## Gemini reviewer transport

### Iterative review

1. Write the raw-artifact bundle.
2. Start `mcp__gemini-review__review_start`.
3. Poll `mcp__gemini-review__review_status` to completion.
4. Save the iterative `threadId`.
5. Use `mcp__gemini-review__review_reply_start` only to verify resolution of
   that reviewer's issue IDs; poll status after each call.

Review Selected-Principle fidelity, target adaptation, minimal faithful
realization, Principle-only closure, named residual gaps, minimal necessary
composition, feasibility, boundaries, the bounded Final Scientific Delta Claim,
and claim-validation obligations. Numeric score is progress metadata, not
acceptance.

### Controller-issued final independent Gate

Do not start a second final blind audit. The Controller-issued
`independent_method_reviewer` is the sole final independent review and receives
the frozen Problem/RCA/Selected-Principle bindings, compact Field Evidence Map,
cited Evidence Cards, current proposal, and constraints without iterative
thread history, scores, or change summaries.

Its only formal outcomes are `METHOD_READY`, `REVISE`, `RETHINK`, `HOLD`, and
`RCA_CONFLICT`:
only `METHOD_READY` advances; `REVISE/HOLD` return to `method_refinement`; and
`RETHINK` returns to `method_design`; `RCA_CONFLICT` returns to
`root_cause_analysis`. Do not manufacture a local acceptance status.
Only the Controller may record `acceptance_status: accepted` after consuming
the bound formal attestation.

## Recovery and rules

Read state, focused Research Contract, active proposal, unresolved issues, and
only the evidence cards named by active issues. Do not reload all historical
rounds.

- Preserve the accepted Problem/RCA and Selected Principle.
- Do not reopen Principle formation or reinterpret convergence locally.
- Add support only for a demonstrated residual adaptation/mechanism gap and
  require real interfaces, compatible activation conditions, boundaries, and
  removal/counterfactual responsibility.
- Allow necessary sophistication; delete only redundancy.
- Never fabricate evidence, results, novelty, scores, or readiness.
- Full Validation requires explicit user initiation and a live Controller
  `validation-handoff`; leave code generation and paper writing downstream.
