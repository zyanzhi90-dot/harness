---
name: "research-refine"
description: "Gemini cross-family review overlay for refining one Certified Problem Contract into a coherent top-journal method route."
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

Preserve the Certified Problem Contract, competing explanations, falsifiable
Scientific Mainline, Design Obligations, minimal sufficient dominant solution,
dominant-only closure, residual-MUST-gap-driven support, necessary integration,
targeted Scientific Closure, and separate novelty verdicts.

Require `CERTIFIED/accepted` and the human-selected
`idea-stage/SELECTED_ROUTE.yaml`; do not treat a prose route or
`IDEA_REPORT.md` as a valid precondition. Final method novelty is checked only
after `FINAL_PROPOSAL.md`.

For each residual `MUST` gap, assess the Field Map and same-field mechanisms
first. Search another field only when those options cannot reasonably close that
gap; combination is permitted only as necessary support and is not the
Scientific Delta.

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

Review Problem Fidelity, competing-explanation discipline, Hypothesis Quality,
obligation traceability, dominant-carrier fit, integration, Scientific Closure,
feasibility, boundaries, Scientific Delta, and targeted validation. Numeric
score is progress metadata, not acceptance.

### Controller-issued final independent Gate

Do not start a second final blind audit. The Controller-issued
`independent_method_reviewer` is the sole final independent review and receives
the frozen problem, compact Field Evidence Map, cited evidence cards, current
proposal, and constraints without iterative thread history, scores, or change
summaries.

Its only formal outcomes are `METHOD_READY`, `REVISE`, `RETHINK`, and `HOLD`:
only `METHOD_READY` advances; `REVISE/HOLD` return to `method_refinement`; and
`RETHINK` returns to `method_design`. Do not manufacture a local acceptance
status.
Only the Controller may record `acceptance_status: accepted` after consuming
the bound formal attestation.

## Recovery and rules

Read state, focused Research Contract, active proposal, unresolved issues, and
only the evidence cards named by active issues. Do not reload all historical
rounds.

- Preserve the certified problem.
- Do not collapse explanations without discriminating evidence.
- Require structural match, transfer limits, real interfaces, compatibility,
  removal/counterfactual failure, and targeted validation.
- Allow necessary sophistication; delete only redundancy.
- Never fabricate evidence, results, novelty, scores, or readiness.
- Leave experiments, code generation, and paper writing unchanged downstream.
