---
name: research-refine
description: Refine one Controller-materialized Selected Principle into a target-adapted, minimal faithful Method and bounded Final Scientific Delta Claim. Use only after accepted Principle convergence; do not use for problem discovery, Principle formation, or pre-convergence test operationalization.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply, mcp__manual_review__review, mcp__manual_review__review_reply
---

# Research Refine

Refine: **$ARGUMENTS**

## Purpose and boundary

Execute the post-convergence scientific sequence:

```text
Selected Principle -> target-domain adaptation -> minimal faithful realization
  -> Principle-only closure -> Residual MUSTs -> minimal necessary composition
  -> FINAL_METHOD_PACKET.json -> deterministic FINAL_PROPOSAL.md
  -> independent final method review
```

Do not enter from a rough Method, prose selection, test-only realization, or
`IDEA_REPORT.md`. Require an active Controller-materialized
`idea-stage/SELECTED_PRINCIPLE.yaml`, accepted Problem/RCA bindings, and the
accepted convergence artifacts. A pre-convergence realization carries only
operationalization/test meaning and is not the Method backbone or composition.

## Required references

Read these once, then execute rather than restating them:

1. [`method-design-contract.md`](../shared-references/method-design-contract.md)
   — verify the accepted Principle and stage semantics.
2. [`method-refinement-protocol.md`](../shared-references/method-refinement-protocol.md)
   — own target adaptation, closure, composition, output, and review.
3. [`root-cause-analysis-contract.md`](../shared-references/root-cause-analysis-contract.md)
   — preserve the accepted causal-chain handoff.
4. [`reviewer-independence.md`](../shared-references/reviewer-independence.md)
   — preserve formal review independence.

Use [`templates/METHOD_PROPOSAL_TEMPLATE.md`](../../templates/METHOD_PROPOSAL_TEMPLATE.md)
as the Packet authoring/view guide. Main writes `FINAL_METHOD_PACKET.json`;
the Controller alone renders `FINAL_PROPOSAL.md` from that validated packet.

## Input preflight

Require and hash-check:

- the active accepted Problem Contract and Evidence Capsule;
- `ROOT_CAUSE_ANALYSIS.json` and `ROOT_CAUSE_VERDICT.json` with
  `DIAGNOSIS_READY`;
- `SELECTED_PRINCIPLE.yaml` materialized by the Controller after accepted
  convergence, including its exact origin/alignment, Target novelty, accepted
  assumptions/predictions, Evidence closure, and Reviewer-accepted boundaries;
- the Controller-exposed return/validation feedback directed to
  `method_refinement`, if any.

Consume the latest feedback before revision. `REVISE`, `HOLD`,
`REVISE_METHOD_DELTA`, final Human `request_revision`, and
`METHOD_REFINEMENT_REQUIRED` preserve the same Selected Principle. `RETHINK`,
`RETHINK_PRINCIPLE_DELTA`, `SELECTED_PRINCIPLE_REJECTED`, `RCA_CONFLICT`,
`NECESSITY_CONFLICT`, `PROBLEM_CONFLICT`, `ROOT_CAUSE_REJECTED`, and
`NECESSITY_PREMISE_REJECTED`, `PROBLEM_PREMISE_REJECTED` reopen upstream science; stop if the Selected
Principle is no longer active. Never rewrite an accepted RCA, Necessity, or
Problem in place to consume conflicting Evidence.

## Configuration

- `MAX_ROUNDS = 5`
- `SCORE_THRESHOLD = 9` — progress signal only, never acceptance.
- `OUTPUT_DIR = refine-logs/`
- `REVIEWER_BACKEND = codex`
- `REVIEWER_MODEL = gpt-5.6-sol`

Allow explicit overrides. Do not hard-code domain doctrine.

## Execution

Follow R0–R7 in `method-refinement-protocol.md`:

- bind the active Problem, RCA, and complete Selected Principle closure without
  drift; use its accepted origin/alignment, novelty, assumptions, predictions,
  Evidence closure, and Reviewer-accepted boundaries as adaptation constraints;
- adapt the algorithm-independent intervention to the target domain;
- construct the minimal faithful realization and attempt Principle-only
  closure against every selected RMC, Capability, Obligation, condition, and
  pre-existing applicability boundary, never an R4-generated
  `CLAIM_RESTRICTION` boundary;
- give every closure subject `CLOSED` or `RESIDUAL_GAP`; only the latter may
  create a stable Residual MUST;
- retain only the smallest mechanisms needed to close those gaps through real
  interfaces;
- form an acyclic causal repair DAG whose core nodes have only accepted Primary
  Root Cause, Target Constraint, or earlier-design incompatibility parents;
- state the Existing-to-New computational relation, current nearest-prior
  separation, Target-only natural derivation, claim-proportional feasibility,
  and one future counterfactual necessity obligation per retained support; for
  each feasibility claim restriction, bind its `boundary_id` to the canonical
  `CLAIM_RESTRICTION` boundary and add that ID to every affected claim
  element's `boundary_refs`, without a `claim_restriction.boundary` text;
- write a bounded `Final Scientific Delta Claim` and traceable
  claim-validation obligations;
- write all scientific facts to `refine-logs/FINAL_METHOD_PACKET.json`; never
  maintain `FINAL_PROPOSAL.md` as an independent truth;
- keep `Established Scientific Delta` unavailable until Full Validation returns
  `VALIDATED`.

If a concrete residual adaptation gap requires literature, open only the
existing `method_refinement` incremental gateway with
`ADAPTATION_GAP_SEARCH`. Bind the active Selected Principle ID/version/hash and
each non-empty residual gap. Complete the search or Evidence re-adoption before
sealing the final review request.

## Reviewer transport

Use the existing iterative reviewer only to create and resolve issue IDs.
Persist path-only review bundles for Codex and equivalent attached/inline
content for a manual backend. Continuity may verify that reviewer's own issues;
it cannot accept the phase.

The Controller-issued `independent_method_reviewer` is the sole formal final
reviewer. When `FINAL_METHOD_PACKET.json` is final and all Evidence work is complete,
invoke:

```text
python -m arisctl --root . refresh-review-request <run_id>
```

Dispatch only against that current request. Write its unchanged formal verdict
to `refine-logs/FINAL_BLIND_REVIEW.md`. Outcomes are:

```text
METHOD_READY -> final_method_novelty_gate
REVISE/HOLD  -> method_refinement
RETHINK      -> method_design
RCA_CONFLICT -> root_cause_analysis
NECESSITY_CONFLICT -> problem_necessity
PROBLEM_CONFLICT   -> problem_generation
NO_GO        -> SCIENTIFIC_NO_GO only for a fatal, Evidence-proven unrecoverable feasibility debt
```

The formal Reviewer returns the most upstream accepted scientific premise that
current formal Evidence actually invalidates. Main analysis, findings,
warnings, and proposed consequences cannot drive a return. Every return verdict
uses non-empty structured `return_guidance` whose `decision_target` is the
canonical phase above. `NO_GO` is forbidden while any fixed recovery, including
Necessity or Problem recovery, remains reasonable.

## Recovery

On resume, read only the focused accepted bindings, `REFINE_STATE.json`, the
current Packet/working proposal, unresolved issue IDs, current Evidence named by those issues,
and the latest return feedback. Older rounds remain audit history.

## Completion rules

- Preserve every selected Principle/RCA/RMC/Capability/Obligation binding.
- Treat `FINAL_METHOD_PACKET.json` as the sole Final Method machine authority;
  accept only the Controller-rendered deterministic Proposal view.
- Keep evidence, inference, proposal, and unvalidated Claim distinct.
- Do not add support without a demonstrated residual adaptation/mechanism gap.
- Do not manufacture Evidence, results, novelty, convergence, or readiness.
- Final Human acceptance does not start validation. Experiment planning and
  execution for Full Validation require an explicit user initiation and a live
  Controller `validation-handoff`.
