---
name: "research-refine"
description: "Refine one Certified Problem Contract or selected problem-derived route into a coherent top-journal method plan. Use when the problem is already certified but its hypothesis, dominant method, integration, or validation needs refinement. Do not use for a vague direction; run idea-creator or idea-discovery first."
---

# Research Refine

Refine: **$ARGUMENTS**

## Purpose

Preserve:

```text
Certified Problem Contract
  -> competing explanations -> falsifiable Scientific Mainline
  -> Design Obligations -> minimal sufficient dominant solution
  -> dominant-only closure -> residual MUST gaps -> necessary completion search
  -> natural integration -> Scientific Closure with minimum claim-validation logic
  -> independent decision
```

For method research, derive capabilities first, start from a minimal sufficient
dominant solution (including first principles where warranted), and search for
support only after dominant-only closure leaves a residual MUST gap.
Check the accepted Field Map and same-field mechanisms first for each declared
residual `MUST` gap; search another field only when they cannot reasonably close
that gap. Combination is permitted only as necessary support, not the default,
Scientific Delta, or novelty verdict.

Stop for a vague, uncertified, provisional, `HOLD`, `REJECT`, or `BLOCKED`
problem. Require `CERTIFIED/accepted`, a hash-matched root-cause analysis and
`DIAGNOSIS_READY` verdict, plus the human-selected
`idea-stage/SELECTED_ROUTE.yaml`; a route mentioned only in prose or in
`IDEA_REPORT.md` is not a valid precondition.

## Required references

Read and follow:

- [`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
- [`root-cause-analysis-contract.md`](../shared-references/root-cause-analysis-contract.md)
- [`method-design-contract.md`](../shared-references/method-design-contract.md)
- [`method-refinement-protocol.md`](../shared-references/method-refinement-protocol.md)
- [`reviewer-independence.md`](../shared-references/reviewer-independence.md)
- [`templates/RESEARCH_CONTRACT_TEMPLATE.md`](../../../templates/RESEARCH_CONTRACT_TEMPLATE.md)
- [`templates/METHOD_PROPOSAL_TEMPLATE.md`](../../../templates/METHOD_PROPOSAL_TEMPLATE.md)

The shared files are the single source of truth. Do not duplicate their
schemas or doctrine here.

## Configuration and outputs

- `MAX_ROUNDS = 5`
- `SCORE_THRESHOLD = 9` — progress signal only
- `OUTPUT_DIR = refine-logs/`
- `REVIEWER_MODEL = gpt-5.6-sol`

Maintain:

- `REFINE_STATE.json`
- `ACTIVE_PROPOSAL.md`
- `UNRESOLVED_ISSUES.md`
- `round-N-review.md`
- `round-N-decision.md`
- `FINAL_BLIND_REVIEW.md`
- `FINAL_PROPOSAL.md`
- `REVIEW_SUMMARY.md`
- `REFINEMENT_REPORT.md`

## Reviewer routing

The base Codex-native reviewer is same-family and its verdict is provisional.

1. Start iterative Round 1 with a fresh secondary reviewer agent.
2. Use the same agent only to check resolution of its own issue IDs.
3. Do not start a second final blind review. The Controller-issued
   `independent_method_reviewer` is the one fresh final independent Gate; it
   receives raw artifacts and no earlier scores, feedback, generator history,
   or change summary.
4. Record the iterative agent ID separately from the Controller review request.
5. Only its `METHOD_READY` may advance; `REVISE/HOLD` return to
   `method_refinement` and `RETHINK` returns to `method_design`.
   Formal acceptance remains Controller-only.

## Workflow

Follow R0-R6 in `method-refinement-protocol.md` without restating it:

- If the selected route exposes a claim-specific evidence gap, open the pending
  `method_refinement` incremental literature window through `arisctl` before
  phase start. Reuse only the existing query/admission/paper-reader/Evidence
  Registry flow, never hosted web search/fetch or a private evidence list; the
  accepted Evidence Card hashes enter the refinement output provenance snapshot.

- R0 locks one Controller-recorded Certified Problem version; it does not make
  the problem permanently immutable.
- R1 executes M0-M6 to build the complete active proposal: recover the
  Scientific Mainline, derive capabilities, close the dominant-only route, then
  search only residual MUST gaps and close the Scientific Delta decision.
- R2 starts the independent iterative review of that proposal.
- R3-R4 resolve issue IDs; score never overrides a blocker.
- R5 runs the sole **Controller-issued final independent review** in a fresh
  context; it is not an additional audit after iterative review.
- R6 writes the canonical outputs and preserves non-READY status honestly.

## Recovery and rules

On resume, read state, the focused Research Contract, active proposal,
unresolved ledger, and evidence cards named by active issues. Do not read every
historical round.

- Preserve the bound Certified Problem ID/version/hash. A material problem
  change must use `arisctl revise-problem`, never a proposal edit.
- Keep evidence, inference, hypothesis, and proposal distinct.
- Keep problem, Scientific Delta, and technical-route novelty separate.
- Allow necessary sophistication; remove redundancy, not required scientific
  links.
- Never fabricate evidence, results, novelty, scores, or readiness.
- Leave experiments, code, and paper writing to downstream skills.
