---
name: "research-refine"
description: "Claude cross-family review overlay for refining one Certified Problem Contract into a coherent top-journal method route. Use after the base Codex research-refine skill when independent Claude review is configured."
---

> Install after `skills/skills-codex/*`.
> `review_independence: cross-family`.

# Research Refine — Claude Review Overlay

Refine: **$ARGUMENTS**

## Scientific contract

Load and follow the base shared references:

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
gap; combination is permitted only as necessary support and is not itself the
Scientific Delta.

## Outputs

Preserve the base interface:

- `REFINE_STATE.json`
- `ACTIVE_PROPOSAL.md`
- `UNRESOLVED_ISSUES.md`
- `round-N-review.md`
- `round-N-decision.md`
- `FINAL_BLIND_REVIEW.md`
- `FINAL_PROPOSAL.md`
- `REVIEW_SUMMARY.md`
- `REFINEMENT_REPORT.md`

## Claude reviewer transport

### Iterative review

1. Write a raw-artifact review bundle containing the frozen problem, compact
   Field Evidence Map, cited evidence cards, active proposal, and constraints.
2. Start `mcp__claude-review__review_start`.
3. Poll `mcp__claude-review__review_status` until complete.
4. Save the iterative `threadId`.
5. Use `mcp__claude-review__review_reply_start` only to check whether that
   reviewer's own issue IDs were resolved; poll status after every call.

Judge:

1. Problem Fidelity;
2. competing-explanation discipline and Hypothesis Quality;
3. obligation traceability;
4. dominant-carrier fit;
5. integration and Scientific Closure;
6. feasibility and boundaries;
7. Scientific Delta and targeted validation.

Numeric score is progress metadata only. Continue while blocking issues remain,
up to `MAX_ROUNDS`.

### Controller-issued final independent Gate

Do not start a second final blind audit. The Controller-issued
`independent_method_reviewer` is the sole final independent review and receives
the clean raw bundle without iterative thread history, scores, feedback,
generator history, or change summaries.

Its only formal outcomes are `METHOD_READY`, `REVISE`, `RETHINK`, and `HOLD`:
only `METHOD_READY` advances; `REVISE/HOLD` return to `method_refinement`; and
`RETHINK` returns to `method_design`. Preserve the corresponding formal
non-ready verdict; do not manufacture a local acceptance status.
Only the Controller may record `acceptance_status: accepted` after consuming
the bound formal attestation.

## Recovery

Read only state, the focused Research Contract, active proposal, unresolved
issues, and evidence cards named by active issues. Do not reload every round or
the full Evidence Registry.

## Rules

- Do not change the certified question, scope, or falsifier.
- Do not collapse plausible explanations without discriminating evidence.
- Require structural match, transfer limits, real interfaces, compatibility,
  removal/counterfactual failure, and targeted validation for borrowed ideas.
- Allow necessary sophistication; delete only redundancy.
- Never fabricate evidence, results, novelty, scores, or readiness.
- Leave experiments, code generation, and paper writing unchanged downstream.
