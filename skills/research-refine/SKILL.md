---
name: research-refine
description: Refine one Certified Problem Contract or already selected problem-derived route into a coherent, top-journal method plan. Use when the problem is already certified but its scientific hypothesis, dominant method, supporting mechanisms, integration, or validation needs rigorous refinement. Do not use for a vague direction; run idea-creator or idea-discovery first.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply, mcp__manual_review__review, mcp__manual_review__review_reply
---

# Research Refine

Refine: **$ARGUMENTS**

## Purpose and boundary

Turn one `CERTIFIED` research problem into a non-redundant complete scientific
closure. Preserve this core:

```text
problem -> competing explanations -> falsifiable scientific mainline
  -> design obligations -> minimal sufficient dominant solution
  -> dominant-only closure -> residual MUST gaps -> necessary completion search
  -> natural integration -> minimum claim-validation logic
  -> independent verdict
```

For method-oriented research, derive required capabilities first, then build the
minimal sufficient dominant solution (including a first-principles solution when
appropriate). Search for transferred or combined support only after its
dominant-only closure leaves a residual MUST gap. Check the accepted Field Map
and same-field mechanisms first; search another field only when they cannot
reasonably close that declared gap. Combination is not a default or a Scientific
Delta/novelty verdict.

Stop and return to problem discovery if the input is vague, uncertified,
provisional, `HOLD`, `REJECT`, or `BLOCKED`. Require
`CERTIFIED/accepted`, a hash-matched `ROOT_CAUSE_ANALYSIS.json` plus
`ROOT_CAUSE_VERDICT.json` with `DIAGNOSIS_READY`, and the explicit human-selected route artifact
`idea-stage/SELECTED_ROUTE.yaml`. A route mentioned only in prose or in
`IDEA_REPORT.md` is not a valid precondition.

## Required references

Read these once, then execute rather than restating them:

1. [`problem-discovery-contract.md`](../shared-references/problem-discovery-contract.md)
   — validate and freeze P3.
2. [`root-cause-analysis-contract.md`](../shared-references/root-cause-analysis-contract.md)
   — validate and freeze the accepted causal-chain handoff.
3. [`method-design-contract.md`](../shared-references/method-design-contract.md)
   — own the Scientific Mainline, obligations, route, integration, Scientific
   Closure, and novelty contracts.
4. [`method-refinement-protocol.md`](../shared-references/method-refinement-protocol.md)
— own the refinement loop, context capsule, state, and final independent Gate.
5. [`reviewer-independence.md`](../shared-references/reviewer-independence.md)
   — own verdict independence.

Read the accepted problem from
[`templates/RESEARCH_CONTRACT_TEMPLATE.md`](../../templates/RESEARCH_CONTRACT_TEMPLATE.md)
and use [`templates/METHOD_PROPOSAL_TEMPLATE.md`](../../templates/METHOD_PROPOSAL_TEMPLATE.md)
for the mutable active proposal. Do not copy the shared doctrine into this skill.

## Configuration

- `MAX_ROUNDS = 5`
- `SCORE_THRESHOLD = 9` — progress signal only; never an acceptance rule.
- `OUTPUT_DIR = refine-logs/`
- `REVIEWER_BACKEND = codex`
- `REVIEWER_MODEL = gpt-5.6-sol`

Allow explicit overrides. Do not hard-code venue-specific physics, control, or
AI rules; retrieve domain evidence only when the active problem requires it.

## Reviewer transport

### Codex backend

- Write Round 1 input to
  `refine-logs/codex_round_1_review_bundle.md`, then prompt:
  `Read the review bundle at <absolute path> and return issue IDs.`
- Start iterative Round 1 with `mcp__codex__codex` in a fresh thread.
- For later issue checks, write
  `refine-logs/codex_round_N_review_bundle.md`, then prompt:
  `Read the re-evaluation bundle at <absolute path> and judge only the saved
  reviewer's issue IDs.`
- Use `mcp__codex__codex-reply` only to verify resolution of that reviewer's
  own issue IDs.
- Do not start a second final blind audit with `mcp__codex__codex`. The
  Controller-issued `independent_method_reviewer` is the one fresh final
  independent Gate; it receives the raw final bundle and live request.
- Write each review bundle to disk and send only its absolute path so the
  reviewer reads raw artifacts.

### Manual backend

- Start iterative review with `mcp__manual_review__review` only. The final
  independent Gate is issued through the Controller, not as a second manual
  blind review.
- Use `review_reply` only inside the iterative resolution loop.
- Attach the same raw bundle or paste it verbatim when the UI cannot read local
  paths.

Record the iterative thread separately from the Controller-issued final review
request. Its raw bundle must not contain generator history, previous scores,
prior reviews, or a summary of changes.

## Workflow

Follow R0-R6 in `method-refinement-protocol.md` without restating its rules:

- If the selected route exposes a claim-specific evidence gap, open the pending
  `method_refinement` incremental literature window through `arisctl` before
  starting refinement. Use only the existing query, admission, paper-reader and
  Evidence Registry flow; never WebSearch/WebFetch or a private evidence list.
  The registered Evidence Card hashes become part of the refinement output's
  Controller provenance snapshot.

- R0 locks one Controller-recorded Certified Problem version; it does not make
  the problem permanently immutable.
- R1 executes M0-M6 to build the complete active proposal: recover the
  Scientific Mainline, derive capability obligations, close the dominant-only
  route, then search only residual MUST gaps and close the separate Scientific
  Delta decision.
- R2 starts the independent iterative review of that proposal.
- R3-R4 maintain one active proposal and resolve issue IDs; score never
  overrides a blocker.
- R5 runs the sole **Controller-issued final independent review** in a fresh
  context. Its formal outcomes are `METHOD_READY -> final_method_novelty_gate`,
  `REVISE/HOLD -> method_refinement`, and `RETHINK -> method_design`.
- R6 writes the canonical outputs and creates `MANIFEST.md` only above the
  shared 15-artifact threshold.

The completion handoff must include `refine-logs/FINAL_BLIND_REVIEW.md` as the
standalone artifact for that sole formal review. The final method-novelty gate
runs only after `METHOD_READY`, against `FINAL_PROPOSAL.md`; an iterative score
never establishes novelty or human acceptance.

## Recovery

On resume, read only:

- `REFINE_STATE.json`;
- the focused Research Contract;
- `ACTIVE_PROPOSAL.md`;
- `UNRESOLVED_ISSUES.md`;
- evidence cards named by unresolved issue IDs.

Do not read all `round-*.md` files. Older rounds are audit history, not active
context.

## Completion rules

- Preserve the bound Certified Problem ID/version/hash in every round. A
  material problem change must use `arisctl revise-problem`, never a proposal edit.
- Keep evidence, inference, hypothesis, and proposed mechanism distinct.
- Keep problem novelty, Scientific Delta novelty, and technical-route novelty
  separate.
- Allow necessary sophistication; remove redundancy, not required scientific
  links.
- Never manufacture evidence, results, novelty, a passing score, or readiness.
- Leave experiment execution, code generation, and paper writing to their
  existing downstream skills.
